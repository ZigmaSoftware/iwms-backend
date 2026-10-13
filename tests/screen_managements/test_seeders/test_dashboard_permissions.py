"""Dashboard screens in the permission seeder: view-only, the Superadmin
Dashboard never seeded into a company catalog, and the Admin Dashboard
granted to Blue Planet's Greater Noida project."""
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
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def _actions(model, screen_name, **scope):
    screen = UserScreen.objects.get(userscreen_name=screen_name, is_deleted=False)
    action_ids = model.objects.filter(
        userscreen_id=screen.unique_id, is_deleted=False, **scope,
    ).values_list("userscreenaction_id", flat=True)
    return set(
        UserScreenAction.objects.filter(unique_id__in=action_ids)
        .values_list("action_name", flat=True)
    )


@pytest.mark.django_db
def test_dashboards_are_view_only_and_superadmin_dashboard_is_not_seeded(company, project):
    PermissionSeeder().run()

    assert _actions(CompanyUserScreenPermission, "admin-dashboard") == {"view"}
    assert UserScreen.objects.filter(
        userscreen_name="superadmin-dashboard", is_active=True, is_deleted=False,
    ).exists()
    assert _actions(CompanyUserScreenPermission, "superadmin-dashboard") == set()


@pytest.mark.django_db
def test_existing_extra_dashboard_grants_are_retired(company, project):
    seeder = PermissionSeeder()
    seeder.run()
    screen = UserScreen.objects.get(userscreen_name="admin-dashboard")
    superadmin_screen = UserScreen.objects.get(userscreen_name="superadmin-dashboard")
    edit = UserScreenAction.objects.get(action_name="edit")
    view = UserScreenAction.objects.get(action_name="view")
    for scr, action in ((screen, edit), (superadmin_screen, view)):
        CompanyUserScreenPermission.objects.create(
            company_id=company.unique_id, project_id=project.unique_id,
            mainscreen_id=scr.mainscreen_id, userscreen_id=scr.unique_id,
            userscreenaction_id=action.unique_id, order_no=99,
        )

    seeder.run()

    assert _actions(CompanyUserScreenPermission, "admin-dashboard") == {"view"}
    assert _actions(CompanyUserScreenPermission, "superadmin-dashboard") == set()


@pytest.mark.django_db
def test_noida_project_gets_the_admin_dashboard():
    company = Company.objects.create(name=PermissionSeeder.NOIDA_COMPANY)
    # Created first, so the baseline catalog lands on this project, not Noida.
    Project.objects.create(name="Other Project", company_id=company.unique_id)
    noida = Project.objects.create(
        name=PermissionSeeder.NOIDA_PROJECT, company_id=company.unique_id,
    )
    config = StaffAccessConfiguration.objects.create(
        staff_id="STC-NOIDA", company_id=company.unique_id, project_ids=noida.unique_id,
    )

    seeder = PermissionSeeder()
    seeder.run()
    seeder.run()

    assert _actions(
        CompanyUserScreenPermission, "admin-dashboard",
        company_id=company.unique_id, project_id=noida.unique_id,
    ) == {"view"}
    assert _actions(
        StaffAccessConfigurationPermission, "admin-dashboard",
        staff_access_configuration_id=config.unique_id,
    ) == {"view"}
