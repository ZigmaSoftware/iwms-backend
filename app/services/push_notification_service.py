"""Firebase Cloud Messaging (FCM) push notifications.

This is intentionally self-gating: if `FIREBASE_CREDENTIALS_PATH` isn't set, or
the file it points to doesn't exist, or `firebase-admin` isn't installed, every
call here becomes a safe no-op (logged once, not raised). This means the rest
of the app — waste collection, status updates, etc. — never breaks because
push isn't configured yet. Once a real Firebase service-account JSON is in
place and the env var points to it, sending "just works" with no other code
changes.

Setup (one-time, ops side):
  1. Create/choose a Firebase project whose registered Android/iOS app package
     name matches this app's `applicationId` / bundle id.
  2. Firebase Console -> Project settings -> Service accounts -> Generate new
     private key. Save the JSON somewhere NOT committed to the repo.
  3. Set `FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json` in .env.
"""

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_app = None
_init_attempted = False
_http_access_token = None
_http_access_token_expires_at = 0


class _UnregisteredToken(Exception):
    pass


def _resolve_customer(customer):
    """Accept either a CustomerCreation instance or one of its public ids."""
    if customer is None or hasattr(customer, "fcm_token"):
        return customer

    from django.db.models import Q

    from app.models.masters.customer_masters.customercreation import CustomerCreation

    customer_id = str(customer).strip()
    if not customer_id:
        return None
    return CustomerCreation.objects.filter(
        Q(unique_id=customer_id) | Q(customer_id=customer_id),
        is_deleted=False,
    ).first()


def _clear_stale_token(owner, token, *, id_field):
    """Clear only the token that FCM rejected, avoiding a refresh race."""
    if owner is None or not getattr(owner, "pk", None):
        return
    type(owner).objects.filter(
        **{id_field: getattr(owner, id_field), "fcm_token": token}
    ).update(fcm_token=None)


def _get_firebase_app():
    """Use Firebase Admin when available, otherwise select HTTP v1 fallback."""
    global _firebase_app, _init_attempted
    if _firebase_app is not None:
        return _firebase_app
    if _init_attempted:
        return None
    _init_attempted = True

    credentials_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or ""
    if not credentials_path:
        logger.error(
            "[push] FIREBASE_CREDENTIALS_PATH is not set; push cannot be sent."
        )
        return None

    try:
        if not os.path.isfile(credentials_path):
            logger.error(
                "[push] FIREBASE_CREDENTIALS_PATH=%s does not exist; push "
                "cannot be sent.",
                credentials_path,
            )
            return None

        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(credentials_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("[push] Firebase Admin initialized for push notifications.")
        return _firebase_app
    except ImportError:
        logger.info(
            "[push] firebase-admin unavailable; using the FCM HTTP v1 sender."
        )
        return None


def _base64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _get_http_access_token():
    """Create a short-lived OAuth token without firebase-admin/grpcio.

    firebase-admin currently cannot be installed on the project's Python 3.14
    environment because grpcio has no compatible wheel. FCM HTTP v1 only needs
    a signed service-account JWT, which cryptography can provide directly.
    """
    global _http_access_token, _http_access_token_expires_at
    now = int(time.time())
    if _http_access_token and now < _http_access_token_expires_at - 60:
        return _http_access_token

    credentials_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or ""
    if not credentials_path or not os.path.isfile(credentials_path):
        raise RuntimeError("Firebase service-account credentials are unavailable.")

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    with open(credentials_path, encoding="utf-8") as credential_file:
        service_account = json.load(credential_file)

    header = _base64url(b'{"alg":"RS256","typ":"JWT"}')
    claims = _base64url(json.dumps({
        "iss": service_account["client_email"],
        "scope": "https://www.googleapis.com/auth/firebase.messaging",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }, separators=(",", ":")).encode())
    unsigned = header + b"." + claims
    private_key = serialization.load_pem_private_key(
        service_account["private_key"].encode(), password=None
    )
    signature = private_key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())
    assertion = (unsigned + b"." + _base64url(signature)).decode()
    token_request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }).encode(),
    )
    with urllib.request.urlopen(token_request, timeout=20) as response:
        token_response = json.load(response)

    _http_access_token = token_response["access_token"]
    _http_access_token_expires_at = now + int(token_response.get("expires_in", 3600))
    return _http_access_token


def _send_via_fcm_http(token, title, body, data):
    credentials_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or ""
    with open(credentials_path, encoding="utf-8") as credential_file:
        project_id = json.load(credential_file)["project_id"]

    payload = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": {str(key): str(value) for key, value in (data or {}).items()},
            "android": {
                "priority": "HIGH",
                "notification": {
                    "channel_id": "iwms_default_channel",
                    "sound": "default",
                },
            },
            "apns": {
                "headers": {"apns-priority": "10", "apns-push-type": "alert"},
                "payload": {"aps": {"sound": "default"}},
            },
        }
    }
    request = urllib.request.Request(
        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {_get_http_access_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
        if not result.get("name"):
            raise RuntimeError("FCM returned no message id.")
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode(errors="replace")
        try:
            error = json.loads(raw_body).get("error", {})
        except json.JSONDecodeError:
            error = {}
        details = error.get("details") or []
        error_code = next(
            (
                detail.get("errorCode")
                for detail in details
                if isinstance(detail, dict) and detail.get("errorCode")
            ),
            None,
        )
        if error_code == "UNREGISTERED":
            raise _UnregisteredToken from exc
        raise RuntimeError(
            f"FCM HTTP {exc.code}: {error_code or error.get('status') or 'unknown'}"
        ) from exc


def _send_message(token, title, body, data):
    app = _get_firebase_app()
    if app is None:
        _send_via_fcm_http(token, title, body, data)
        return

    from firebase_admin import messaging

    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
        data={str(k): str(v) for k, v in (data or {}).items()},
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="iwms_default_channel",
                sound="default",
            ),
        ),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10", "apns-push-type": "alert"},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default"),
            ),
        ),
    )
    try:
        messaging.send(message, app=app)
    except messaging.UnregisteredError as exc:
        raise _UnregisteredToken from exc
    except Exception:
        logger.exception("[push] Failed to initialize Firebase Admin.")
        return None


def send_push_to_customer(customer, title, body, data=None):
    """Send a push notification to a single customer's registered device.

    Safe to call unconditionally from any code path (signals, viewsets): it
    never raises. Returns True if a message was actually sent, False otherwise
    (no token, push not configured, or the send failed).
    """
    customer = _resolve_customer(customer)
    if customer is None:
        logger.warning(
            "[push] Customer could not be resolved; notification skipped."
        )
        return False

    token = getattr(customer, "fcm_token", None)
    if not token:
        logger.info(
            "[push] Customer %s has no registered FCM token.",
            getattr(customer, "unique_id", "unknown"),
        )
        return False

    try:
        _send_message(token, title, body, data)
        return True
    except _UnregisteredToken:
        _clear_stale_token(customer, token, id_field="unique_id")
        logger.warning(
            "[push] Removed stale FCM token for customer %s.",
            getattr(customer, "unique_id", "unknown"),
        )
        return False
    except Exception:
        logger.exception(
            "[push] Failed to send push to customer %s",
            getattr(customer, "unique_id", customer),
        )
        return False


def send_push_to_staff(staff, title, body, data=None):
    """Send a push notification to a single staff member's registered device
    (driver/operator/supervisor apps). Same contract as
    `send_push_to_customer`: never raises, returns True only on an actual send.
    """
    if staff is None:
        return False

    token = getattr(staff, "fcm_token", None)
    if not token:
        return False

    try:
        _send_message(token, title, body, data)
        return True
    except _UnregisteredToken:
        _clear_stale_token(staff, token, id_field="staff_unique_id")
        logger.warning(
            "[push] Removed stale FCM token for staff %s.",
            getattr(staff, "staff_unique_id", "unknown"),
        )
        return False
    except Exception:
        logger.exception(
            "[push] Failed to send push to staff %s",
            getattr(staff, "staff_unique_id", staff),
        )
        return False
