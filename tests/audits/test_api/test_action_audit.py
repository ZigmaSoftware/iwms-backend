"""ActionAuditMixin: write requests that no CRUD hook audits (mobile
endpoints on plain ViewSets, custom @actions) still leave a CommonAudit row."""
import pytest
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from app.utils.audit_mixin import ActionAuditMixin, write_common_audit
from app.utils.common_audit import CommonAudit


class _MobileViewSet(ActionAuditMixin, viewsets.ViewSet):
    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        return Response({"status": "success", "data": {"unique_id": "TRIP-1"}})

    @action(detail=False, methods=["post"], url_path="fail")
    def fail(self, request):
        return Response({"status": "error", "message": "Trip not started"}, status=400)

    @action(detail=False, methods=["post"], url_path="explicit")
    def explicit(self, request):
        write_common_audit(request, module_name="m", endpoint_name="e")
        return Response({"ok": True})

    @action(detail=False, methods=["get"], url_path="read")
    def read(self, request):
        return Response({"ok": True})

    @action(detail=False, methods=["post"], url_path="register-fcm-token")
    def register_fcm_token(self, request):
        return Response({"status": "ok"})


factory = APIRequestFactory()


@pytest.fixture
def user(superuser):
    return superuser


def _call(name, method, user, path, data=None):
    view = _MobileViewSet.as_view({method: name})
    request = getattr(factory, method)(path, data or {}, format="json")
    force_authenticate(request, user=user)
    return view(request)


@pytest.mark.django_db
class TestActionAudit:
    def test_successful_mobile_action_is_audited(self, user):
        _call("start", "post", user, "/api/v1/operator-mobile/trip-lifecycle/start/",
              {"assignment_id": "TRIP-1", "password": "secret"})
        row = CommonAudit.objects.get()
        assert row.module_name == "operator-mobile"
        assert row.endpoint_name == "trip-lifecycle/start"
        assert row.method == "POST"
        assert row.success is True
        assert row.object_id == "TRIP-1"
        assert row.new_data["password"] == "[REDACTED]"

    def test_rejected_action_records_failure_reason(self, user):
        _call("fail", "post", user, "/api/v1/operator-mobile/trip-lifecycle/fail/")
        row = CommonAudit.objects.get()
        assert row.success is False
        assert row.reason == "Trip not started"

    def test_explicit_audit_is_not_duplicated(self, user):
        _call("explicit", "post", user, "/api/v1/operator-mobile/x/explicit/")
        assert CommonAudit.objects.count() == 1

    def test_reads_and_token_registration_are_not_audited(self, user):
        _call("read", "get", user, "/api/v1/operator-mobile/x/read/")
        _call("register_fcm_token", "post", user,
              "/api/v1/staff-creations/staffcreation/register-fcm-token/",
              {"fcm_token": "abc"})
        assert CommonAudit.objects.count() == 0
