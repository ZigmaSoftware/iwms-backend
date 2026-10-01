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
from app.utils.audit_mixin import AuditViewSetMixin, format_audit_error, get_client_ip
from app.utils.common_audit import CommonAudit

PERMISSION_AUDIT_BASE = "/api/v1/audits/permission-audit/"
COMMON_AUDIT_BASE = "/api/v1/audits/common-audit/"


def _company_grant(company, action, project=None, screen="US-1"):
    return CompanyUserScreenPermission.objects.create(
        company_id=company.unique_id,
        project_id=project,
        mainscreen_id="MS-1",
        userscreen_id=screen,
        userscreenaction_id=action,
        order_no=1,
    )


def _run_company_view(user, method, change, status=200):
    """Run `change` inside a write request on a view with the mixin."""
    from rest_framework.response import Response
    from rest_framework.test import force_authenticate
    from rest_framework.views import APIView

    from app.utils.permission_snapshot import CompanyPermissionAuditMixin

    class GrantView(CompanyPermissionAuditMixin, APIView):
        def _handle(self, request):
            change()
            return Response({}, status=status)

        post = put = patch = delete = _handle

    request = getattr(APIRequestFactory(), method.lower())("/grant/")
    force_authenticate(request, user=user)
    return GrantView.as_view()(request)


@pytest.mark.django_db
class TestCompanyPermissionAudit:
    def test_one_row_per_request_with_old_and_new(self, company, superuser):
        for action in ("ACT-USE", "ACT-EDIT"):
            _company_grant(company, action, project="PRJ-1")

        def change():
            for action in ("ACT-ADD", "ACT-DELETE"):
                _company_grant(company, action, project="PRJ-1")
            # Bulk write: fires no model signals, must still be audited.
            CompanyUserScreenPermission.objects.filter(
                userscreenaction_id="ACT-EDIT"
            ).update(is_active=False, is_deleted=True)

        _run_company_view(superuser, "POST", change)

        row = PermissionAuditLog.objects.get()
        assert row.source == "COMPANY_SCREEN"
        assert row.http_method == "POST"
        assert row.action_type == "UPDATED"
        assert row.company_id == company.unique_id
        assert row.project_id == "PRJ-1"
        assert row.updated_by == superuser.unique_id

        def actions(snapshot):
            return sorted(
                a["id"] for m in snapshot["modules"] for s in m["screens"] for a in s["actions"]
            )

        assert actions(row.old_permissions) == ["ACT-EDIT", "ACT-USE"]
        assert actions(row.new_permissions) == ["ACT-ADD", "ACT-DELETE", "ACT-USE"]

    def test_each_project_gets_its_own_row(self, company, superuser):
        def change():
            _company_grant(company, "ACT-USE", project="PRJ-1")
            _company_grant(company, "ACT-USE", project="PRJ-2")

        _run_company_view(superuser, "PUT", change)

        rows = PermissionAuditLog.objects.order_by("project_id")
        assert [(r.project_id, r.action_type, r.http_method) for r in rows] == [
            ("PRJ-1", "CREATED", "PUT"),
            ("PRJ-2", "CREATED", "PUT"),
        ]

    def test_failed_request_writes_nothing(self, company, superuser):
        _run_company_view(
            superuser, "POST", lambda: _company_grant(company, "ACT-USE"), status=400
        )
        assert not PermissionAuditLog.objects.exists()

    def test_column_grants_are_audited(self, company, superuser):
        from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
            CompanyUserScreenColumnPermission,
        )

        _run_company_view(
            superuser,
            "PATCH",
            lambda: CompanyUserScreenColumnPermission.objects.create(
                company_id=company.unique_id, userscreen_id="US-1", column_id="COL-1"
            ),
        )

        row = PermissionAuditLog.objects.get()
        assert row.source == "COMPANY_COLUMN"
        assert row.new_permissions["modules"][0]["screens"][0]["actions"] == [
            {"id": "COL-1", "name": "COL-1"}
        ]


def _grant(config, *actions, screen="US-1", module="MS-1"):
    for action in actions:
        StaffAccessConfigurationPermission.objects.create(
            staff_access_configuration_id=config.unique_id,
            mainscreen_id=module,
            userscreen_id=screen,
            userscreenaction_id=action,
        )


def _revoke(config, action):
    StaffAccessConfigurationPermission.objects.filter(
        staff_access_configuration_id=config.unique_id, userscreenaction_id=action
    ).update(is_deleted=True, is_active=False)


class _StubSerializer:
    """Stands in for the access serializer: save() applies `change`."""

    def __init__(self, instance, change, validated_data=None):
        self.instance = instance
        self.change = change
        self.validated_data = validated_data or {}

    def save(self):
        self.change(self.instance)
        return self.instance


def _viewset(viewset_class, user, method):
    viewset = viewset_class()
    viewset.request = SimpleNamespace(user=user, method=method)
    return viewset


@pytest.mark.django_db
class TestAccessSaveAudit:
    def test_staff_save_is_one_row_with_old_and_new(self, company, superuser):
        from app.viewsets.superadmin.staff_management.staff_access_configuration_viewset import (
            StaffAccessConfigurationViewSet,
        )

        config = StaffAccessConfiguration.objects.create(
            staff_id="STF-1", company_id=company.unique_id, project_ids="PRJ-1"
        )
        _grant(config, "ACT-1", "ACT-2")

        def change(instance):
            _revoke(instance, "ACT-1")
            _grant(instance, "ACT-3", "ACT-4", screen="US-2", module="MS-2")

        _viewset(StaffAccessConfigurationViewSet, superuser, "PATCH").perform_update(
            _StubSerializer(config, change)
        )

        row = PermissionAuditLog.objects.get()
        assert row.source == "STAFF_ACCESS"
        assert row.http_method == "PATCH"
        assert row.action_type == "UPDATED"
        assert row.target_id == "STF-1"
        assert row.project_id == "PRJ-1"
        assert row.updated_by == superuser.unique_id

        old_actions = [a["id"] for a in row.old_permissions["modules"][0]["screens"][0]["actions"]]
        assert old_actions == ["ACT-1", "ACT-2"]
        new_modules = {m["id"]: m for m in row.new_permissions["modules"]}
        assert set(new_modules) == {"MS-1", "MS-2"}
        assert [a["id"] for a in new_modules["MS-1"]["screens"][0]["actions"]] == ["ACT-2"]

    def test_unchanged_save_writes_nothing(self, company, superuser):
        from app.viewsets.superadmin.staff_management.staff_access_configuration_viewset import (
            StaffAccessConfigurationViewSet,
        )

        config = StaffAccessConfiguration.objects.create(
            staff_id="STF-1", company_id=company.unique_id
        )
        _grant(config, "ACT-1")

        _viewset(StaffAccessConfigurationViewSet, superuser, "PUT").perform_update(
            _StubSerializer(config, lambda instance: None)
        )

        assert not PermissionAuditLog.objects.exists()

    def test_staff_delete_records_everything_revoked(self, company, superuser):
        from app.viewsets.superadmin.staff_management.staff_access_configuration_viewset import (
            StaffAccessConfigurationViewSet,
        )

        config = StaffAccessConfiguration.objects.create(
            staff_id="STF-1", company_id=company.unique_id, app_module_id="APP-DRV"
        )
        _grant(config, "ACT-1")

        _viewset(StaffAccessConfigurationViewSet, superuser, "DELETE").perform_destroy(config)

        row = PermissionAuditLog.objects.get()
        assert row.action_type == "DELETED"
        assert row.http_method == "DELETE"
        assert row.old_permissions["app_modules"] == [{"id": "APP-DRV", "name": "APP-DRV"}]
        assert row.new_permissions == {"app_modules": [], "modules": []}

    def test_customer_first_save_is_created(self, company, superuser):
        from app.viewsets.masters.customer_masters.customer_access_configuration_viewset import (
            CustomerAccessConfigurationViewSet,
        )

        config = CustomerAccessConfiguration(customer_id="CUS-1", company_id=company.unique_id)

        def change(instance):
            instance.app_modules = ["APP-CIT"]
            instance.app_screens = ["US-A"]
            instance.save()

        _viewset(CustomerAccessConfigurationViewSet, superuser, "POST").perform_create(
            _StubSerializer(config, change, {"resolved_customer": SimpleNamespace(unique_id="CUS-1")})
        )

        row = PermissionAuditLog.objects.get()
        assert row.source == "CUSTOMER_ACCESS"
        assert row.action_type == "CREATED"
        assert row.http_method == "POST"
        assert row.new_permissions["modules"][0]["screens"] == [
            {"id": "US-A", "name": "US-A", "actions": []}
        ]

    def test_api_summarises_the_change(self, auth_client, company):
        PermissionAuditLog.objects.create(
            source="STAFF_ACCESS",
            company_id=company.unique_id,
            http_method="PATCH",
            old_permissions={"app_modules": [], "modules": [
                {"id": "MS-1", "name": "masters", "screens": [
                    {"id": "US-1", "name": "plants", "actions": [
                        {"id": "ACT-1", "name": "add"}, {"id": "ACT-2", "name": "edit"},
                    ]},
                ]},
            ]},
            new_permissions={"app_modules": [{"id": "APP-DRV", "name": "Driver"}], "modules": [
                {"id": "MS-1", "name": "masters", "screens": [
                    {"id": "US-1", "name": "plants", "actions": [{"id": "ACT-2", "name": "edit"}]},
                ]},
            ]},
        )

        row = auth_client.get(PERMISSION_AUDIT_BASE).data["results"][0]

        assert row["http_method"] == "PATCH"
        assert row["granted_count"] == 1
        assert row["revoked_count"] == 1
        assert row["changed_modules"] == ["App Access", "masters"]
        assert row["source_label"] == "Staff Access Configuration"

    def test_staff_filter_includes_older_rows(self, auth_client, company):
        PermissionAuditLog.objects.create(company_id=company.unique_id, source="STAFF_ACCESS")
        PermissionAuditLog.objects.create(company_id=company.unique_id, source="STAFF_SCREEN")
        PermissionAuditLog.objects.create(company_id=company.unique_id, source="COMPANY_SCREEN")

        rows = auth_client.get(PERMISSION_AUDIT_BASE, {"source": "staff_access"}).data["results"]
        assert sorted(r["source"] for r in rows) == ["STAFF_ACCESS", "STAFF_SCREEN"]

        sources = auth_client.get(f"{PERMISSION_AUDIT_BASE}filter-options/").data["sources"]
        assert [o["unique_id"] for o in sources] == list(PermissionAuditLog.CURRENT_SOURCES)


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


@pytest.mark.django_db
class TestMergeLegacyPermissionAudit:
    def _legacy(self, action, active, at):
        row = PermissionAuditLog.objects.create(
            source="STAFF_SCREEN",
            target_id="STF-1",
            mainscreen_id="MS-1",
            userscreen_id="US-1",
            userscreenaction_id=action,
            is_active=active,
            action_type="CREATED" if active else "DELETED",
        )
        PermissionAuditLog.objects.filter(pk=row.pk).update(timestamp=at)

    def test_rows_become_one_snapshot_per_save(self, company):
        from datetime import timedelta

        from django.core.management import call_command
        from django.utils import timezone

        config = StaffAccessConfiguration.objects.create(
            staff_id="STF-1", company_id=company.unique_id
        )
        _grant(config, "ACT-2", "ACT-3")  # access as it stands now

        start = timezone.now() - timedelta(minutes=5)
        # Save 1: granted ACT-1 and ACT-2.
        self._legacy("ACT-1", True, start)
        self._legacy("ACT-2", True, start + timedelta(milliseconds=5))
        # Save 2, a minute later: revoked ACT-1, granted ACT-3.
        self._legacy("ACT-1", False, start + timedelta(minutes=1))
        self._legacy("ACT-3", True, start + timedelta(minutes=1, milliseconds=5))

        call_command("merge_legacy_permission_audit")

        rows = list(PermissionAuditLog.objects.order_by("timestamp"))
        assert [r.source for r in rows] == ["STAFF_ACCESS", "STAFF_ACCESS"]

        def actions(snapshot):
            return sorted(
                a["id"] for m in snapshot["modules"] for s in m["screens"] for a in s["actions"]
            )

        first, second = rows
        assert first.action_type == "CREATED"
        assert actions(first.old_permissions) == []
        assert actions(first.new_permissions) == ["ACT-1", "ACT-2"]
        assert second.action_type == "UPDATED"
        assert actions(second.old_permissions) == ["ACT-1", "ACT-2"]
        assert actions(second.new_permissions) == ["ACT-2", "ACT-3"]
        assert second.timestamp == start + timedelta(minutes=1, milliseconds=5)

    def test_company_rows_merge_per_company_project(self, company):
        from django.core.management import call_command

        _company_grant(company, "ACT-USE", project="PRJ-1")  # live access now
        for action in ("ACT-USE", "ACT-EDIT"):
            PermissionAuditLog.objects.create(
                source="COMPANY_SCREEN",
                company_id=company.unique_id,
                project_id="PRJ-1",
                mainscreen_id="MS-1",
                userscreen_id="US-1",
                userscreenaction_id=action,
                is_active=action == "ACT-USE",
                http_method="POST",
            )

        call_command("merge_legacy_permission_audit")

        row = PermissionAuditLog.objects.get()
        assert (row.source, row.project_id, row.http_method) == ("COMPANY_SCREEN", "PRJ-1", "POST")
        old = [a["id"] for a in row.old_permissions["modules"][0]["screens"][0]["actions"]]
        new = [a["id"] for a in row.new_permissions["modules"][0]["screens"][0]["actions"]]
        assert (old, new) == (["ACT-EDIT"], ["ACT-USE"])
