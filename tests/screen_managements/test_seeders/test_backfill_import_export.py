"""backfill_import_export_permissions: add -> import, view -> export on the
company catalog and staff grants, idempotently, never on view-only screens."""
from io import StringIO

import pytest
from django.core.management import call_command

from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.mainscreentype import MainScreenType
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)


def _names(model, screen, **scope):
    ids = model.objects.filter(
        userscreen_id=screen.unique_id, is_deleted=False, **scope
    ).values_list("userscreenaction_id", flat=True)
    return set(
        UserScreenAction.objects.filter(unique_id__in=ids).values_list(
            "action_name", flat=True
        )
    )


@pytest.mark.django_db
def test_backfill_grants_import_and_export(company, project):
    actions = {
        name: UserScreenAction.objects.create(action_name=name, variable_name=name)
        for name in ("view", "add", "edit")
    }
    stype = MainScreenType.objects.create(type_name="masters")
    main = MainScreen.objects.create(
        mainscreen_name="transport-masters", mainscreentype_id=stype.unique_id, order_no=1
    )
    fuels = UserScreen.objects.create(
        userscreen_name="fuels", mainscreen_id=main.unique_id, order_no=1,
        folder_name="fuels", icon_name="fuels",
    )
    dash = UserScreen.objects.create(
        userscreen_name="admin-dashboard", mainscreen_id=main.unique_id, order_no=2,
        folder_name="admin-dashboard", icon_name="admin-dashboard",
    )
    for screen, names in ((fuels, ("view", "add", "edit")), (dash, ("view",))):
        for order, name in enumerate(names, start=1):
            CompanyUserScreenPermission.objects.create(
                company_id=company.unique_id,
                project_id=project.unique_id,
                mainscreen_id=main.unique_id,
                userscreen_id=screen.unique_id,
                userscreenaction_id=actions[name].unique_id,
                order_no=order,
                description=f"{name} {screen.userscreen_name}",
            )
    config = StaffAccessConfiguration.objects.create(
        staff_id="STAFF-1", company_id=company.unique_id
    )
    StaffAccessConfigurationPermission.objects.create(
        staff_access_configuration_id=config.unique_id,
        mainscreen_id=main.unique_id,
        userscreen_id=fuels.unique_id,
        userscreenaction_id=actions["view"].unique_id,
    )

    # Dry run writes nothing.
    call_command("backfill_import_export_permissions", stdout=StringIO())
    assert not UserScreenAction.objects.filter(action_name="import").exists()

    call_command("backfill_import_export_permissions", "--apply", stdout=StringIO())
    call_command("backfill_import_export_permissions", "--apply", stdout=StringIO())

    assert _names(CompanyUserScreenPermission, fuels) == {
        "view", "add", "edit", "import", "export",
    }
    # Dashboards are view-only in the catalog.
    assert _names(CompanyUserScreenPermission, dash) == {"view"}
    staff = {"staff_access_configuration_id": config.unique_id}
    assert _names(StaffAccessConfigurationPermission, fuels, **staff) == {
        "view", "export",
    }
    # Idempotent: one row per grant.
    assert CompanyUserScreenPermission.objects.filter(
        userscreen_id=fuels.unique_id, is_deleted=False
    ).count() == 5
