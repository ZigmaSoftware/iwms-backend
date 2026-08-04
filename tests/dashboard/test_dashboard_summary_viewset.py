"""API tests for the company/project-scoped dashboard summary endpoint."""
import pytest

from app.models.customers.customercreation import CustomerCreation
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty

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
    return Project.objects.create(name="Other Project", company_id=other_company)


@pytest.fixture
def company_user(db, company, project):
    """A regular (non-superadmin) user scoped to `company`/`project`."""
    from app.models.superadmin_masters.auth_user import User
    return User.objects.create_user(
        username="company_user_test",
        password="testpass123",
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def company_auth_client(api_client, company_user):
    """APIClient authenticated as a non-superadmin, company-scoped user."""
    from rest_framework_simplejwt.tokens import AccessToken
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
        company_id=company,
        project_id=project,
        country=country,
        state=state,
        district=district,
        city=city,
        zone=zone,
        ward=ward,
        property_ref=prop,
        sub_property=sub_prop,
    )


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardSummaryAuth:
    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)


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
