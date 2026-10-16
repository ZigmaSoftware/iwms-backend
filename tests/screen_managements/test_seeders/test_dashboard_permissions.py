"""Dashboard screens in the permission seeder: view-only, the Superadmin
Dashboard never seeded into a company catalog, and the Admin and User
Dashboard screens left for a super admin to approve per company/project."""
import pytest

from app.management.commands.seeders.superadmin.screen_management.permissions import (
    PermissionSeeder,
)
from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.utils.permission_catalog import APPROVAL_REQUIRED_SCREENS


def _actions(model, screen_name, **scope):
    screen = UserScreen.objects.get(userscreen_name=screen_name, is_deleted=False)
    action_ids = model.objects.filter(
        userscreen_id=screen.unique_id, is_deleted=False, **scope,
    ).values_list("userscreenaction_id", flat=True)
    return set(
        UserScreenAction.objects.filter(unique_id__in=action_ids)
        .values_list("action_name", flat=True)
    )


DASHBOARDS = (
    "admin-dashboard",
    "home-dashboard",
    "dashboard-grievances",
    "dashboard-reports",
    "dashboard-weighbridge",
)


def _approve(company, project, screen_name, action_name="view"):
    screen = UserScreen.objects.get(userscreen_name=screen_name, is_deleted=False)
    CompanyUserScreenPermission.objects.create(
        company_id=company.unique_id, project_id=project.unique_id,
        mainscreen_id=screen.mainscreen_id, userscreen_id=screen.unique_id,
        userscreenaction_id=UserScreenAction.objects.get(action_name=action_name).unique_id,
        order_no=1,
    )


def test_dashboards_need_super_admin_approval():
    assert set(DASHBOARDS) <= APPROVAL_REQUIRED_SCREENS


@pytest.mark.django_db
def test_seeder_lists_dashboards_but_enables_none(company, project):
    config = StaffAccessConfiguration.objects.create(
        staff_id="STC-1", company_id=company.unique_id, project_ids=project.unique_id,
    )
    PermissionSeeder().run()

    for name in DASHBOARDS + ("superadmin-dashboard",):
        assert UserScreen.objects.filter(
            userscreen_name=name, is_active=True, is_deleted=False,
        ).exists(), name
        assert _actions(CompanyUserScreenPermission, name) == set(), name
        assert _actions(
            StaffAccessConfigurationPermission, name,
            staff_access_configuration_id=config.unique_id,
        ) == set(), name


@pytest.mark.django_db
def test_approved_dashboard_survives_reseeding_view_only(company, project):
    seeder = PermissionSeeder()
    seeder.run()
    _approve(company, project, "admin-dashboard", "view")
    _approve(company, project, "admin-dashboard", "edit")
    _approve(company, project, "home-dashboard", "view")
    _approve(company, project, "superadmin-dashboard", "view")

    seeder.run()

    assert _actions(CompanyUserScreenPermission, "admin-dashboard") == {"view"}
    assert _actions(CompanyUserScreenPermission, "home-dashboard") == {"view"}
    assert _actions(CompanyUserScreenPermission, "dashboard-reports") == set()
    assert _actions(CompanyUserScreenPermission, "superadmin-dashboard") == set()
