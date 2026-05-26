"""
Shared fixtures and factories for all unit tests.
"""
import pytest
from django.db import connection
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.masters.areatype import AreaType
from app.models.role_assigns.userType import UserType
from app.models.superadmin_masters.auth_user import User
from app.utils.common_audit import CommonAudit


@pytest.fixture(scope="session", autouse=True)
def create_audit_table(django_db_setup, django_db_blocker):
    """Create the common_audit table (not in app models, so not auto-created)."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as schema_editor:
            try:
                schema_editor.create_model(CommonAudit)
            except Exception:
                pass  # table may already exist in the in-memory db across sessions


# ─────────────────────────────────────────────
# Tenant fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def company(db):
    return Company.objects.create(name="Test Company", description="A test company")


@pytest.fixture
def project(db, company):
    from app.models.superadmin_masters.project import Project
    return Project.objects.create(name="Test Project", company_id=company)


# ─────────────────────────────────────────────
# Geographic hierarchy fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def continent(db):
    return Continent.objects.create(name="Asia")


@pytest.fixture
def country(db, continent):
    return Country.objects.create(
        name="India",
        continent_id=continent,
        currency="INR",
        mob_code="+91",
    )


@pytest.fixture
def state(db, continent, country):
    return State.objects.create(
        name="Tamil Nadu",
        label="TN",
        continent_id=continent,
        country_id=country,
    )


@pytest.fixture
def district(db, continent, country, state):
    return District.objects.create(
        name="Chennai",
        continent_id=continent,
        country_id=country,
        state_id=state,
    )


@pytest.fixture
def city(db, company, project, continent, country, state, district):
    from app.models.masters.city import City
    return City.objects.create(
        name="Chennai City",
        continent_id=continent,
        country_id=country,
        state_id=state,
        district_id=district,
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def area_type(db, continent, country, state, district, city):
    return AreaType.objects.create(
        name="Urban",
        state_id=state,
        district_id=district,
        city_id=city,
    )


@pytest.fixture
def zone(db, state, district, city):
    return Zone.objects.create(
        zone_name="Zone 1",
        state_id=state,
        district_id=district,
        city_id=city,
    )


@pytest.fixture
def ward(db, state, district, city, zone):
    from app.models.masters.ward import Ward
    return Ward.objects.create(
        ward_name="Ward 1",
        state_id=state,
        district_id=district,
        city_id=city,
        zone_id=zone,
    )


# ─────────────────────────────────────────────
# Role / user fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def user_type(db):
    return UserType.objects.create(name="Staff")


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin_test",
        password="testpass123",
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, superuser):
    """APIClient authenticated as superuser via JWT."""
    from rest_framework_simplejwt.tokens import AccessToken
    token = AccessToken.for_user(superuser)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client
