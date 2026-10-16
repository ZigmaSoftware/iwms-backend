import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.services import push_notification_service as push_service


class _Payload:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _fake_firebase_admin(send):
    messaging = SimpleNamespace(
        Message=_Payload,
        Notification=_Payload,
        AndroidConfig=_Payload,
        AndroidNotification=_Payload,
        APNSConfig=_Payload,
        APNSPayload=_Payload,
        Aps=_Payload,
        UnregisteredError=type("UnregisteredError", (Exception,), {}),
        send=send,
    )
    module = ModuleType("firebase_admin")
    module.messaging = messaging
    return module, messaging


@pytest.mark.django_db
def test_customer_id_is_resolved_and_sends_cross_platform_payload(
    household_customer, monkeypatch
):
    household_customer.fcm_token = "customer-device-token"
    household_customer.save(update_fields=["fcm_token"])
    sent = []
    firebase_admin, _ = _fake_firebase_admin(
        lambda message, app: sent.append((message, app))
    )
    monkeypatch.setitem(sys.modules, "firebase_admin", firebase_admin)
    monkeypatch.setattr(push_service, "_get_firebase_app", lambda: "firebase-app")

    delivered = push_service.send_push_to_customer(
        household_customer.unique_id,
        "Waste collected",
        "2 kg of wet waste collected.",
        data={"event": "household_collected", "weight": 2},
    )

    assert delivered is True
    assert len(sent) == 1
    message, app = sent[0]
    assert app == "firebase-app"
    assert message.token == "customer-device-token"
    assert message.data == {"event": "household_collected", "weight": "2"}
    assert message.android.priority == "high"
    assert message.android.notification.channel_id == "iwms_default_channel"
    assert message.apns.headers["apns-push-type"] == "alert"


@pytest.mark.django_db
def test_unregistered_customer_token_is_cleared(household_customer, monkeypatch):
    household_customer.fcm_token = "stale-token"
    household_customer.save(update_fields=["fcm_token"])
    firebase_admin, messaging = _fake_firebase_admin(None)

    def reject(message, app):
        raise messaging.UnregisteredError("token is no longer registered")

    messaging.send = reject
    monkeypatch.setitem(sys.modules, "firebase_admin", firebase_admin)
    monkeypatch.setattr(push_service, "_get_firebase_app", lambda: "firebase-app")

    delivered = push_service.send_push_to_customer(
        household_customer,
        "Waste collected",
        "Collection complete.",
    )

    assert delivered is False
    household_customer.refresh_from_db()
    assert household_customer.fcm_token is None
