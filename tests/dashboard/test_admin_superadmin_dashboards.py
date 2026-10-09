"""Admin Dashboard (dashboards/admin) and Superadmin Dashboard (dashboards/superadmin)."""
from datetime import date, time
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from app.middleware import module_permission_middleware as mpm
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.permission_catalog import (
    ROUTE_OWNERS,
    SCREEN_STRUCTURE,
    SUPERADMIN_ONLY_ROUTES,
)
from app.viewsets.dashboard.admin_dashboard_viewset import AdminDashboardViewSet
from app.viewsets.dashboard.superadmin_dashboard_viewset import SuperadminDashboardViewSet

ADMIN = "/api/v1/dashboards/admin/"
SUPERADMIN = "/api/v1/dashboards/superadmin/"


def _trip(company, project, day, status=DailyTripAssignment.STATUS_COMPLETED):
    return DailyTripAssignment.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        trip_date=day,
        scheduled_time=time(6, 0),
        status=status,
    )


@pytest.fixture
def other_project(db, company):
    return Project.objects.create(name="Second Project", company_id=company.unique_id)


@pytest.fixture
def other_company(db):
    company = Company.objects.create(name="Other Company")
    Project.objects.create(name="Other Project", company_id=company.unique_id)
    return company


@pytest.fixture
def trips(db, company, project, other_project, other_company):
    other = Project.objects.get(company_id=other_company.unique_id)
    _trip(company, project, date(2026, 10, 1))
    _trip(company, project, date(2026, 10, 2), DailyTripAssignment.STATUS_SCHEDULED)
    _trip(company, other_project, date(2026, 10, 2))
    _trip(other_company, other, date(2026, 10, 2))


# ------------------------------------------------------------ catalog

def test_admin_dashboard_is_a_grantable_screen():
    assert ROUTE_OWNERS["dashboards/admin"] == ("dashboard", "admin-dashboard")


def test_superadmin_dashboard_is_listed_but_not_grantable():
    assert "superadmin-dashboard" in SCREEN_STRUCTURE["dashboard"]
    assert "dashboards/superadmin" in SUPERADMIN_ONLY_ROUTES
    assert "dashboards/superadmin" in mpm.PLATFORM_SUPERADMIN_ROUTES
    assert "dashboards/superadmin" not in ROUTE_OWNERS


# ------------------------------------------------------ admin dashboard

@pytest.mark.django_db
def test_superadmin_sees_every_company_by_default(auth_client, trips):
    data = auth_client.get(ADMIN, {"from_date": "2026-10-01", "to_date": "2026-10-02"}).json()
    assert data["operations"]["trips"]["total"] == 4
    assert data["filters"]["can_pick_company"] is True
    assert [row["trips"] for row in data["daily"]] == [1, 3]


@pytest.mark.django_db
def test_company_and_project_filters(auth_client, trips, company, project):
    params = {"from_date": "2026-10-01", "to_date": "2026-10-02", "company_id": company.unique_id}
    assert auth_client.get(ADMIN, params).json()["operations"]["trips"]["total"] == 3

    data = auth_client.get(ADMIN, {**params, "project_id": project.unique_id}).json()
    trips = data["operations"]["trips"]
    assert (trips["total"], trips["completed"], trips["completion_rate"]) == (2, 1, 50.0)
    assert data["scope"]["project_name"] == "Test Project"
    assert [row["project_id"] for row in data["projects"]] == [project.unique_id]


@pytest.mark.django_db
def test_several_companies_and_projects(
    auth_client, trips, company, project, other_project, other_company,
):
    params = {"from_date": "2026-10-01", "to_date": "2026-10-02"}
    both = f"{company.unique_id},{other_company.unique_id}"
    data = auth_client.get(ADMIN, {**params, "company_id": both}).json()
    assert data["operations"]["trips"]["total"] == 4
    assert sorted(data["scope"]["company_ids"]) == sorted(both.split(","))
    assert len(data["filters"]["projects"]) == 3

    picked = f"{project.unique_id},{other_project.unique_id}"
    data = auth_client.get(ADMIN, {**params, "company_id": both, "project_id": picked}).json()
    assert data["operations"]["trips"]["total"] == 3
    assert sorted(data["scope"]["project_ids"]) == sorted(picked.split(","))
    assert {row["project_id"] for row in data["projects"]} == set(picked.split(","))


@pytest.mark.django_db
def test_day_wise_view(auth_client, trips):
    data = auth_client.get(ADMIN, {"date": "2026-10-01"}).json()
    assert data["scope"]["days"] == 1
    assert data["operations"]["trips"]["total"] == 1


@pytest.mark.django_db
def test_master_counts_are_split_per_project(auth_client, company, project, other_project):
    from app.models.masters.zone import Zone

    Zone.objects.create(zone_name="North", company_id=company.unique_id, project_id=project.unique_id)
    Zone.objects.create(zone_name="South", company_id=company.unique_id, project_id=other_project.unique_id)
    masters = {
        row["key"]: row
        for row in auth_client.get(ADMIN, {"company_id": company.unique_id}).json()["masters"]
    }
    assert masters["zones"]["total"] == 2
    assert masters["zones"]["by_project"] == {project.unique_id: 1, other_project.unique_id: 1}
    assert masters["vehicle_types"]["level"] == "global"


@pytest.mark.django_db
def test_company_user_is_pinned_to_company_and_allowed_projects(
    trips, company, project, other_company,
):
    StaffAccessConfiguration.objects.create(
        staff_id="STC-1", company_id=company.unique_id, project_ids=project.unique_id,
    )
    user = SimpleNamespace(
        is_authenticated=True, is_superuser=False,
        company_id=company.unique_id, staff_unique_id="STC-1",
    )
    request = APIRequestFactory().get(ADMIN, {
        "from_date": "2026-10-01", "to_date": "2026-10-02",
        # Both are ignored: another tenant, and a project outside the config.
        "company_id": other_company.unique_id,
    })
    force_authenticate(request, user=user)
    data = AdminDashboardViewSet.as_view({"get": "list"})(request).data
    assert data["scope"]["company_name"] == "Test Company"
    assert data["filters"]["can_pick_company"] is False
    assert [p["id"] for p in data["filters"]["projects"]] == [project.unique_id]
    # Their one project is preselected and cannot be changed.
    assert data["filters"]["can_pick_project"] is False
    assert data["scope"]["project_ids"] == [project.unique_id]
    assert data["scope"]["project_name"] == "Test Project"
    assert data["operations"]["trips"]["total"] == 2


def _middleware(monkeypatch, path, permissions, view_class=AdminDashboardViewSet, **user):
    request = APIRequestFactory().get(path)
    user = {"is_superuser": False, "company_id": "CMP-1", **user}

    def _auth(req):
        req.user = SimpleNamespace(is_authenticated=True, **user)

    monkeypatch.setattr(mpm, "_authenticate_request", _auth)
    monkeypatch.setattr(mpm, "_resolve_permissions_for_request", lambda req: permissions)
    view = SimpleNamespace(cls=view_class, actions={"get": "list"})
    return mpm.ModulePermissionMiddleware(lambda r: None).process_view(request, view, (), {})


def test_admin_dashboard_needs_its_view_grant(monkeypatch):
    assert _middleware(monkeypatch, ADMIN, {"dashboard": {"admin-dashboard": ["view"]}}) is None
    for permissions in (
        {},
        {"customers": {"customercreations": ["view"]}},
        {"dashboard": {"admin-dashboard": ["add", "edit"]}},
    ):
        denied = _middleware(monkeypatch, ADMIN, permissions)
        assert denied.status_code == 403, permissions


def test_admin_dashboard_filters_do_not_bypass_the_grant(monkeypatch):
    path = f"{ADMIN}?company_id=CMP-2&project_id=PRJ-9&from_date=2026-01-01"
    assert _middleware(monkeypatch, path, {}).status_code == 403


def test_platform_super_admin_passes_the_middleware(monkeypatch):
    assert _middleware(monkeypatch, ADMIN, {}, is_superuser=True, company_id=None) is None
    assert _middleware(
        monkeypatch, SUPERADMIN, {}, SuperadminDashboardViewSet, is_superuser=True, company_id=None,
    ) is None


@pytest.mark.parametrize("user", [
    {},  # company staff
    {"is_superuser": True},  # superuser tied to a company
])
def test_superadmin_dashboard_is_refused_by_the_middleware(monkeypatch, user):
    granted = {
        "dashboard": {"admin-dashboard": ["view"], "superadmin-dashboard": ["view"]},
        "dashboards": {"superadmin": ["view"], "SuperadminDashboard": ["view"]},
    }
    for path in (SUPERADMIN, f"{SUPERADMIN}?date=2026-10-01"):
        denied = _middleware(monkeypatch, path, granted, SuperadminDashboardViewSet, **user)
        assert denied.status_code == 403
        assert b"Platform super admin only" in denied.content


# ------------------------------------------------- superadmin dashboard

@pytest.mark.django_db
def test_superadmin_dashboard_lists_companies_and_projects(auth_client, trips, company):
    data = auth_client.get(SUPERADMIN, {"from_date": "2026-10-01", "to_date": "2026-10-02"}).json()
    assert data["platform"]["companies"] == 2
    assert data["platform"]["projects"] == 3
    rows = {row["company_name"]: row for row in data["companies"]}
    assert rows["Test Company"]["projects"] == 2
    assert rows["Test Company"]["trips"] == 3
    assert rows["Other Company"]["trips"] == 1
    assert {"catalog", "company_grants", "staff_grants", "changes"} <= set(data["permissions"])


@pytest.mark.django_db
def test_superadmin_dashboard_refuses_company_users(api_client, company, project):
    from rest_framework_simplejwt.tokens import AccessToken

    from app.models.superadmin_masters.auth_user import User

    user = User.objects.create_user(
        username="company_admin", password="x",
        company_id=company.unique_id, project_id=project.unique_id,
    )
    token = AccessToken.for_user(user)
    token["unique_id"] = user.unique_id
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api_client.get(SUPERADMIN).status_code == 403


# --------------------------------------------------------------- seeder

@pytest.mark.django_db
def test_seeder_gives_admin_dashboard_to_every_grant_holder(company):
    from app.management.commands.seeders.superadmin.screen_management.permissions import (
        PermissionSeeder,
    )
    from app.models.superadmin.screen_management.companyuserscreenpermission import (
        CompanyUserScreenPermission,
    )
    from app.models.superadmin.screen_management.mainscreen import MainScreen
    from app.models.superadmin.screen_management.mainscreentype import MainScreenType
    from app.models.superadmin.screen_management.userscreen import UserScreen
    from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
    from app.models.superadmin.staff_management.staff_access_configuration import (
        StaffAccessConfigurationPermission,
    )

    kind = MainScreenType.objects.create(type_name="masters")
    main = MainScreen.objects.create(
        mainscreen_name="customers", icon_name="customers", mainscreentype_id=kind.unique_id, order_no=1,
    )
    customers = UserScreen.objects.create(
        mainscreen_id=main.unique_id, userscreen_name="customercreations",
        folder_name="customercreations", icon_name="customercreations", order_no=1,
    )
    dash_main = MainScreen.objects.create(
        mainscreen_name="dashboard", icon_name="dashboard", mainscreentype_id=kind.unique_id, order_no=2,
    )
    dashboard = UserScreen.objects.create(
        mainscreen_id=dash_main.unique_id, userscreen_name="admin-dashboard",
        folder_name="admin-dashboard", icon_name="admin-dashboard", order_no=1,
    )
    view = UserScreenAction.objects.create(action_name="view", variable_name="view")
    add = UserScreenAction.objects.create(action_name="add", variable_name="add")
    CompanyUserScreenPermission.objects.create(
        company_id=company.unique_id, mainscreen_id=main.unique_id,
        userscreen_id=customers.unique_id, userscreenaction_id=add.unique_id, order_no=1,
    )
    StaffAccessConfigurationPermission.objects.create(
        staff_access_configuration_id="SAC-1", mainscreen_id=main.unique_id,
        userscreen_id=customers.unique_id, userscreenaction_id=add.unique_id,
    )

    PermissionSeeder()._inherit_grants(dashboard, "*")

    assert CompanyUserScreenPermission.objects.filter(
        company_id=company.unique_id, userscreen_id=dashboard.unique_id,
        userscreenaction_id=view.unique_id,
    ).exists()
    assert StaffAccessConfigurationPermission.objects.filter(
        staff_access_configuration_id="SAC-1", userscreen_id=dashboard.unique_id,
        userscreenaction_id=view.unique_id,
    ).exists()
