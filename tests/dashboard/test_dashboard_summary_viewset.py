"""API tests for the company/project-scoped dashboard summary endpoint."""
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory

from app.middleware import module_permission_middleware as mpm
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty

BASE = "/api/v1/dashboard/summary/"


# ─────────────────────────────────────────────
# Local fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def prop(db):
    return Property.objects.create(property_name="Residential")


@pytest.fixture
def sub_prop(db, prop):
    return SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)


@pytest.fixture
def other_company(db):
    from app.models.superadmin_masters.company import Company
    return Company.objects.create(name="Other Company", description="Another tenant")


@pytest.fixture
def other_project(db, other_company):
    from app.models.superadmin_masters.project import Project
    return Project.objects.create(name="Other Project", company_id=other_company.unique_id)


@pytest.fixture
def company_user(db, company, project):
    """A regular (non-superadmin) user scoped to `company`/`project`."""
    from app.models.superadmin_masters.auth_user import User
    return User.objects.create_user(
        username="company_user_test",
        password="testpass123",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )


@pytest.fixture
def company_auth_client(api_client, company_user, monkeypatch):
    """APIClient authenticated as a non-superadmin, company-scoped user
    holding the user-dashboard/home-dashboard grant."""
    from rest_framework_simplejwt.tokens import AccessToken
    monkeypatch.setattr(
        mpm, "_resolve_permissions_for_request",
        lambda req: {"user-dashboard": {"home-dashboard": ["view"]}},
    )
    token = AccessToken.for_user(company_user)
    token["unique_id"] = company_user.unique_id
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


def _make_customer(*, company, project, country, state, district, city, zone, ward, prop, sub_prop, name, contact_no):
    return CustomerCreation.objects.create(
        customer_name=name,
        contact_no=contact_no,
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no=f"ID-{contact_no}",
        company_id=company.unique_id,
        project_id=project.unique_id,
        country_id=country.unique_id,
        state_id=state.unique_id,
        district_id=district.unique_id,
        city_id=city.unique_id,
        zone_id=zone.unique_id,
        ward_id=ward.unique_id,
        property_id=prop.unique_id,
        sub_property_id=sub_prop.unique_id,
    )


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardSummaryAuth:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)


def _middleware(monkeypatch, path, permissions, view_name):
    request = APIRequestFactory().get(path)

    def _auth(req):
        req.user = SimpleNamespace(is_authenticated=True, is_superuser=False, company_id="CMP-1")

    monkeypatch.setattr(mpm, "_authenticate_request", _auth)
    monkeypatch.setattr(mpm, "_resolve_permissions_for_request", lambda req: permissions)
    view = SimpleNamespace(cls=type(view_name, (), {}), actions={"get": "list"})
    return mpm.ModulePermissionMiddleware(lambda r: None).process_view(request, view, (), {})


def test_summary_needs_the_home_dashboard_grant(monkeypatch):
    granted = {"user-dashboard": {"home-dashboard": ["view"]}}
    assert _middleware(monkeypatch, BASE, granted, "DashboardSummaryViewSet") is None
    for permissions in (
        {},
        {"customers": {"customercreations": ["view"]}},
        {"user-dashboard": {"dashboard-grievances": ["view"]}},
    ):
        denied = _middleware(monkeypatch, BASE, permissions, "DashboardSummaryViewSet")
        assert denied.status_code == 403, permissions


@pytest.mark.parametrize("screen, path, view_name", [
    ("dashboard-grievances", "/api/v1/complaint-ticket/tickets/", "ComplaintTicketViewSet"),
    ("dashboard-reports", "/api/v1/reports/daily-waste-comparisons/", "DailyWasteComparisonViewSet"),
    ("dashboard-reports", "/api/v1/reports/monthly-waste-comparison/", "MonthlyWasteComparisonReportViewSet"),
    ("home-dashboard", "/api/v1/complaint-ticket/tickets/", "ComplaintTicketViewSet"),
    # Weighbridge Log's unknown-vehicle check. Also guards the route parser,
    # which once dropped every "v..." route.
    ("dashboard-weighbridge", "/api/v1/transport-masters/vehicle-creation/", "VehicleCreationViewSet"),
])
def test_dashboard_tabs_read_the_data_they_show(monkeypatch, screen, path, view_name):
    granted = {"user-dashboard": {screen: ["view"]}}
    assert _middleware(monkeypatch, path, granted, view_name) is None
    assert _middleware(monkeypatch, path, {}, view_name).status_code == 403


@pytest.mark.django_db
class TestDashboardSummaryCompanyScoping:
    def test_company_user_ignores_mismatched_company_id_param(
        self,
        company_auth_client,
        company,
        project,
        other_company,
        other_project,
        continent,
        country,
        state,
        district,
        city,
        zone,
        ward,
        prop,
        sub_prop,
    ):
        _make_customer(
            company=company, project=project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Own Customer", contact_no="9000000001",
        )
        _make_customer(
            company=other_company, project=other_project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Other Tenant Customer", contact_no="9000000002",
        )

        resp = company_auth_client.get(
            BASE, {"company_id": other_company.unique_id, "project_id": project.unique_id}
        )

        assert resp.status_code == 200
        assert resp.data["summary"]["households"]["total_customers"] == 1


@pytest.mark.django_db
class TestDashboardSummarySuperadmin:
    def test_superadmin_scopes_by_explicit_params(
        self,
        auth_client,
        company,
        project,
        other_company,
        other_project,
        continent,
        country,
        state,
        district,
        city,
        zone,
        ward,
        prop,
        sub_prop,
    ):
        _make_customer(
            company=company, project=project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Scoped Customer", contact_no="9000000003",
        )
        _make_customer(
            company=other_company, project=other_project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Unscoped Customer", contact_no="9000000004",
        )

        resp = auth_client.get(BASE, {"company_id": company.unique_id, "project_id": project.unique_id})

        assert resp.status_code == 200
        assert resp.data["summary"]["households"]["total_customers"] == 1

    def test_superadmin_without_params_returns_zeroed_summary_not_cross_tenant_leak(
        self,
        auth_client,
        company,
        project,
        continent,
        country,
        state,
        district,
        city,
        zone,
        ward,
        prop,
        sub_prop,
    ):
        _make_customer(
            company=company, project=project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Some Customer", contact_no="9000000005",
        )

        resp = auth_client.get(BASE)

        assert resp.status_code == 200
        assert resp.data["summary"]["households"]["total_customers"] == 0


@pytest.mark.django_db
class TestDashboardSummaryEmptyData:
    def test_no_data_seeded_returns_zeroed_structures(self, company_auth_client, project):
        resp = company_auth_client.get(BASE, {"project_id": project.unique_id})

        assert resp.status_code == 200
        data = resp.data

        assert data["summary"]["households"] == {
            "total_customers": 0, "collected": 0, "not_available": 0, "not_collected": 0,
        }
        assert data["summary"]["attendance"] == {"total": 0, "present": 0, "absent": 0, "leave": 0}
        assert data["summary"]["bins"] == {"total": 0, "collected": 0, "not_collected": 0}
        assert data["summary"]["vehicles"] == {"total": 0, "active": 0, "inactive": 0}
        assert data["summary"]["grievances"] == {"total": 0, "open": 0, "in_progress": 0, "resolved": 0}
        assert data["summary"]["waste"]["total_kg"] == 0.0
        assert data["summary"]["waste"]["waste_type_breakdown"] == []
        assert data["summary"]["operations"]["available"] is True
        assert data["summary"]["operations"]["trips_total"] == 0
        assert data["recent_grievances"] == []
        assert data["critical_alerts"] == []
        assert data["vehicle_performance"] == []
        assert data["trip_performance"] == []
        assert data["team_performance"] == []
        assert data["ward_performance"] == []
        assert len(data["collection_progress"]) == 31
        assert data["vehicle_status_detail"] == {"idle": 0, "breakdown": 0, "offline_gps": 0}
        assert data["filters"]["wards"] == []
        assert "as_of" in data


@pytest.mark.django_db
class TestDashboardSummaryNonZeroCounts:
    def test_households_reflect_seeded_customers(
        self,
        company_auth_client,
        company,
        project,
        other_company,
        other_project,
        continent,
        country,
        state,
        district,
        city,
        zone,
        ward,
        prop,
        sub_prop,
    ):
        _make_customer(
            company=company, project=project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Customer One", contact_no="9000000006",
        )
        _make_customer(
            company=company, project=project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Customer Two", contact_no="9000000007",
        )
        _make_customer(
            company=other_company, project=other_project, country=country, state=state,
            district=district, city=city, zone=zone, ward=ward,
            prop=prop, sub_prop=sub_prop, name="Customer Three", contact_no="9000000008",
        )

        resp = company_auth_client.get(BASE, {"project_id": project.unique_id})

        assert resp.status_code == 200
        assert resp.data["summary"]["households"]["total_customers"] == 2
