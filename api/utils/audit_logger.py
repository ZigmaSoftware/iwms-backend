# api/utils/audit_logger.py

import jwt
from django.conf import settings

from api.apps.auditlog import AuditLog
from api.apps.userCreation import User
from api.utils.audit_context_resolver import resolve_audit_context
from api.utils.audit_id_resolver import get_audit_ids


def create_audit_log(request, view_func, success, reason=None):
    ctx = resolve_audit_context(request, view_func)
    if not ctx:
        return None

    audit_ids = get_audit_ids(**ctx)
    if not audit_ids:
        return None

    mainscreen_id, userscreen_id, userscreenaction_id = audit_ids
    if not (mainscreen_id and userscreen_id and userscreenaction_id):
        return None

    user = _resolve_request_user(request)
    if not user:
        return None

    try:
        log = AuditLog.objects.create(
            user_id_id=user.unique_id,
            staffusertype_id_id=getattr(user, "staffusertype_id_id", None),

            mainscreen_id=mainscreen_id,
            userscreen_id=userscreen_id,
            userscreenaction_id=userscreenaction_id,

            success=success,
            reason=reason,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )
    except Exception:
        # Audit logging should never block business operations.
        return None

    return {
        "unique_id": log.unique_id,
        "success": log.success,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "mainscreen_id": log.mainscreen_id_id,
        "userscreen_id": log.userscreen_id_id,
        "userscreenaction_id": log.userscreenaction_id_id,
    }


def _resolve_request_user(request):
    user = getattr(request, "user", None)
    if getattr(user, "unique_id", None):
        return user

    payload = getattr(request, "jwt_payload", None)
    if not payload:
        token = _extract_token(request)
        if token:
            payload = _decode_token(token)

    if not payload:
        return None

    unique_id = payload.get("unique_id")
    if not unique_id:
        return None

    try:
        return User.objects.only("unique_id", "staffusertype_id_id").get(
            unique_id=unique_id
        )
    except User.DoesNotExist:
        return None


def _extract_token(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return auth_header.strip() or None


def _decode_token(token):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
