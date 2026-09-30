"""API/signal tests for the Permission Audit trail and CommonAudit request context."""
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.utils.audit_context import permission_audit_actor
from app.utils.audit_mixin import AuditViewSetMixin, format_audit_error, get_client_ip
from app.utils.common_audit import CommonAudit

PERMISSION_AUDIT_BASE = "/api/v1/audits/permission-audit/"
COMMON_AUDIT_BASE = "/api/v1/audits/common-audit/"


@pytest.mark.django_db
class TestPermissionAuditSignal:
    def test_create_then_revoke_records_previous_state(self, company):
        perm = CompanyUserScreenPermission.objects.create(
            company_id=company.unique_id, mainscreen_id="MS-1", order_no=1
        )
        created = PermissionAuditLog.objects.get(action_type="CREATED")
        assert created.company_id == company.unique_id
        assert created.previous_is_active is None

        perm.is_active = False
        perm.save()

        updated = PermissionAuditLog.objects.get(action_type="UPDATED")
        assert updated.previous_is_active is True
        assert updated.is_active is False


@pytest.mark.django_db
class TestStaffAndCustomerAccessAudit:
    def test_staff_screen_grant_and_revoke(self, company):
        config = StaffAccessConfiguration.objects.create(
            staff_id="STF-1", company_id=company.unique_id, project_ids="PRJ-1"
        )
        with permission_audit_actor(SimpleNamespace(is_authenticated=True, unique_id="USR-1")):
            grant = StaffAccessConfigurationPermission.objects.create(
                staff_access_configuration_id=config.unique_id,
                mainscreen_id="MS-1",
                userscreen_id="US-1",
                userscreenaction_id="ACT-1",
            )
        created = PermissionAuditLog.objects.get(source="STAFF_SCREEN")
        assert created.action_type == "CREATED"
        assert created.target_id == "STF-1"
        assert created.company_id == company.unique_id
        assert created.project_id == "PRJ-1"
        assert created.userscreenaction_id == "ACT-1"
        assert created.updated_by == "USR-1"

        grant.is_deleted = True
        grant.is_active = False
        grant.save(update_fields=["is_deleted", "is_active"])

        revoked = PermissionAuditLog.objects.get(source="STAFF_SCREEN", action_type="DELETED")
        assert revoked.previous_is_active is True
        assert revoked.is_active is False

    def test_staff_app_change_logs_revoke_and_grant(self, company):
        config = StaffAccessConfiguration.objects.create(
            staff_id="STF-1", company_id=company.unique_id, app_module_id="APP-DRV"
        )
        config.app_module_id = "APP-SUP"
        config.save(update_fields=["app_module_id"])

        rows = PermissionAuditLog.objects.filter(source="STAFF_APP").order_by("id")
        assert [(r.app_module_id, r.action_type) for r in rows] == [
            ("APP-DRV", "CREATED"),
            ("APP-DRV", "DELETED"),
            ("APP-SUP", "CREATED"),
        ]

        config.description = "no app change"
        config.save()
        assert PermissionAuditLog.objects.filter(source="STAFF_APP").count() == 3

    def test_customer_modules_and_screens_diffed(self, company):
        config = CustomerAccessConfiguration.objects.create(
            customer_id="CUS-1",
            company_id=company.unique_id,
            app_modules=["APP-CIT"],
            app_screens=["US-A", "US-B"],
        )
        assert PermissionAuditLog.objects.filter(
            source="CUSTOMER_SCREEN", action_type="CREATED"
        ).count() == 2

        config.app_screens = ["US-B", "US-C"]
        config.save(update_fields=["app_screens"])

        changes = set(
            PermissionAuditLog.objects.filter(source="CUSTOMER_SCREEN")
            .exclude(userscreen_id__in=["US-A", "US-B"], action_type="CREATED")
            .values_list("userscreen_id", "action_type")
        )
        assert changes == {("US-A", "DELETED"), ("US-C", "CREATED")}

        config.delete()
        app_rows = PermissionAuditLog.objects.filter(source="CUSTOMER_APP")
        assert list(app_rows.values_list("action_type", flat=True).order_by("id")) == [
            "CREATED",
            "DELETED",
        ]
        assert all(r.target_id == "CUS-1" for r in app_rows)

    def test_api_filters_by_source(self, auth_client, company):
        PermissionAuditLog.objects.create(company_id=company.unique_id, source="STAFF_SCREEN")
        PermissionAuditLog.objects.create(company_id=company.unique_id, source="COMPANY_SCREEN")

        resp = auth_client.get(PERMISSION_AUDIT_BASE, {"source": "staff_screen"})

        rows = resp.data.get("results", resp.data)
        assert [r["source"] for r in rows] == ["STAFF_SCREEN"]
        assert rows[0]["source_label"] == "Staff Access Configuration"


@pytest.mark.django_db
class TestPermissionAuditAPI:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(PERMISSION_AUDIT_BASE)
        assert resp.status_code in (401, 403)

    def test_list_filters_by_action_type(self, auth_client, company):
        PermissionAuditLog.objects.create(company_id=company.unique_id, action_type="CREATED")
        PermissionAuditLog.objects.create(company_id=company.unique_id, action_type="DELETED")

        resp = auth_client.get(PERMISSION_AUDIT_BASE, {"action_type": "deleted"})

        assert resp.status_code == 200
        rows = resp.data.get("results", resp.data)
        assert [r["action_type"] for r in rows] == ["DELETED"]
        assert rows[0]["company_name"] == company.name

    def test_list_is_server_paginated(self, auth_client, company):
        for _ in range(12):
            PermissionAuditLog.objects.create(company_id=company.unique_id)

        resp = auth_client.get(PERMISSION_AUDIT_BASE, {"page": 2, "limit": 5})

        assert resp.status_code == 200
        assert resp.data["count"] == 12
        assert resp.data["page"] == 2
        assert resp.data["total_pages"] == 3
        assert len(resp.data["results"]) == 5

    def test_filter_options(self, auth_client, company):
        PermissionAuditLog.objects.create(company_id=company.unique_id)

        resp = auth_client.get(f"{PERMISSION_AUDIT_BASE}filter-options/")

        assert resp.status_code == 200
        assert resp.data["companies"] == [
            {"unique_id": company.unique_id, "name": company.name}
        ]

    def test_is_read_only(self, auth_client):
        resp = auth_client.post(PERMISSION_AUDIT_BASE, {}, format="json")
        assert resp.status_code == 405


@pytest.mark.django_db
class TestCommonAuditRequestContext:
    def test_success_filter(self, auth_client):
        CommonAudit.objects.create(module_name="m", endpoint_name="e", method="POST")
        CommonAudit.objects.create(
            module_name="m", endpoint_name="e", method="POST", success=False, reason="bad"
        )

        resp = auth_client.get(COMMON_AUDIT_BASE, {"success": "false"})

        rows = resp.data.get("results", resp.data)
        assert [r["reason"] for r in rows] == ["bad"]

    def test_failed_create_is_audited_and_reraised(self, superuser):
        class Base:
            def perform_create(self, serializer):
                raise ValidationError({"name": ["This field is required."]})

        class View(AuditViewSetMixin, Base):
            AUDIT_MODULE = "masters"
            AUDIT_ENDPOINT = "wards"

        request = APIRequestFactory().post(
            "/", REMOTE_ADDR="10.0.0.5", HTTP_USER_AGENT="pytest"
        )
        request.user = superuser
        view = View()
        view.request = request

        class Serializer:
            initial_data = {"name": ""}
            instance = None

        with pytest.raises(ValidationError):
            view.perform_create(Serializer())

        row = CommonAudit.objects.get()
        assert row.success is False
        assert row.reason == "name: This field is required."
        assert row.ip_address == "10.0.0.5"
        assert row.user_agent == "pytest"
        assert row.new_data == {"name": ""}


def test_get_client_ip_rejects_garbage_forwarded_for():
    request = APIRequestFactory().get("/", HTTP_X_FORWARDED_FOR="not-an-ip")
    assert get_client_ip(request) is None


def test_format_audit_error_plain_exception():
    assert format_audit_error(RuntimeError("boom")) == "boom"
