"""Only an explicit App Module selection grants mobile access.

`supervisor_user` — a Company Supervisor with no Staff Access Configuration at
all — could still sign into the Supervisor app, because the permission
resolver used to infer a surface from the role *name*: "Company Supervisor"
contains "supervisor", so it returned `["supervisor"]`, the login gate saw a
non-empty list and let them through. An admin who had granted nothing had in
fact granted an app, and the web screen showing "No app access" was telling
the truth about the configuration while the app disagreed.

These pin the rule down: the app is whatever somebody explicitly selected on
the access configuration, and nothing else implies one.
"""

import pytest
from rest_framework import serializers

from app.models.screen_managements.app_module import AppModule
from app.models.staff_creations.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.serializers.login.login_serializer import LoginSerializer
from app.utils.permission_response import resolve_permission_payload


@pytest.fixture
def supervisor_module(db):
    return AppModule.objects.create(
        module_key="app-supervisor",
        surface_key="supervisor",
        label="Supervisor",
        route="/supervisor/home",
        order_no=4,
    )


@pytest.fixture
def company(db):
    return Company.objects.create(name="Blue Planet")


def _payload_for_staff(staff):
    return resolve_permission_payload(
        company_unique_id=getattr(staff.company_id, "unique_id", None),
        staff_unique_id=staff.staff_unique_id,
        role_name="Company Supervisor",
        user_type="staff",
        app_module=staff.app_module,
    )


def test_supervisor_role_name_alone_grants_no_app(db, company):
    """The regression: no configuration means no app, whatever the role."""
    staff = Staffcreation.objects.create(
        employee_name="supervisor_user", company_id=company,
    )
    payload = _payload_for_staff(staff)

    assert payload["app_modules"] == []
    assert payload["app_surfaces"] == []


def test_configuration_without_a_selection_grants_no_app(
    db, company, supervisor_module
):
    """A configuration that exists but selects no app is still a refusal."""
    staff = Staffcreation.objects.create(
        employee_name="supervisor_user", company_id=company,
    )
    StaffAccessConfiguration.objects.create(
        staff_id=staff, company_id=company, app_module=None,
    )

    assert _payload_for_staff(staff)["app_modules"] == []


def test_explicit_selection_grants_that_app(db, company, supervisor_module):
    staff = Staffcreation.objects.create(
        employee_name="supervisor_user", company_id=company,
    )
    StaffAccessConfiguration.objects.create(
        staff_id=staff, company_id=company, app_module=supervisor_module,
    )

    payload = _payload_for_staff(staff)
    assert payload["app_modules"] == ["supervisor"]
    assert [s["key"] for s in payload["app_surfaces"]] == ["supervisor"]


def test_legacy_citizen_fallback_still_works(db):
    """Customers are passed a literal "citizen" before their access
    configuration is backfilled, and must keep signing in."""
    payload = resolve_permission_payload(
        company_unique_id=None,
        role_name="customer",
        user_type="customer",
        app_module="citizen",
    )
    assert payload["app_modules"] == ["citizen"]


@pytest.mark.parametrize("client", ["mobile", "app", "android", "ios"])
def test_gate_refuses_mobile_sign_in_without_an_app(client):
    with pytest.raises(serializers.ValidationError) as exc:
        LoginSerializer()._enforce_app_module_gate(
            {"client": client}, {"app_modules": []},
        )
    assert "no mobile app access" in str(exc.value).lower()


def test_gate_leaves_web_sign_in_alone():
    """A browser is not an app — web sign-in must not be gated on a module."""
    LoginSerializer()._enforce_app_module_gate({"client": "web"}, {"app_modules": []})
