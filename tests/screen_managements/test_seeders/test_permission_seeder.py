import pytest

from app.management.commands.seeders.superadmin.screen_management.permissions import (
    PermissionSeeder,
)
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.userscreen import UserScreen


EXPECTED_GROUPS = {
    "super-admin": [
        "screen-managements",
        "role-assigns",
        "user-creations",
        "common-masters",
        "audits",
        "process",
    ],
    "masters": [
        "masters",
        "waste-types",
        "transport-masters",
        "customers",
    ],
    "core-modules": [
        "schedule-setup",
        "schedule-operations",
        "complaint-ticket",
    ],
    "reports": [
        "schedule-masters",
        "reports",
    ],
}

EXPECTED_SIDEBAR_SCREENS = {
    "screen-managements": {
        "mainscreentype",
        "mainscreens",
        "userscreens",
        "userscreen-action",
        "companywisescreenpermissions",
    },
    "user-creations": {"staffcreation", "staff-access-configuration"},
    "schedule-setup": {
        "staff-templates",
        "alternative-staff-templates",
        "collection-points",
        "trip-plans",
    },
    "schedule-operations": {
        "daily-trip-assignments",
        "daily-trip-collection-points",
        "bin-collection-events",
        "daily-trip-logs",
        "wastecollections",
        "vehicle-breakdowns",
        "retrip-requests",
    },
    "complaint-ticket": {"tickets", "categories", "subcategories"},
    "audits": {"common-audit", "login-audit"},
}


@pytest.mark.django_db
def test_permission_seeder_groups_modules_like_the_admin_sidebar(company, project):
    legacy_type = MainScreenType.objects.create(type_name="megamenu")
    MainScreen.objects.create(
        mainscreentype_id=legacy_type,
        mainscreen_name="schedule-setup",
        icon_name="schedule-setup",
        order_no=1,
    )

    seeder = PermissionSeeder()
    seeder.run()
    seeder.run()

    for group_name, expected_modules in EXPECTED_GROUPS.items():
        screen_type = MainScreenType.objects.get(type_name=group_name)
        actual_modules = list(
            MainScreen.objects.filter(mainscreentype_id=screen_type)
            .order_by("order_no")
            .values_list("mainscreen_name", flat=True)
        )
        assert actual_modules == expected_modules

    for module_name, expected_screens in EXPECTED_SIDEBAR_SCREENS.items():
        actual_screens = set(
            UserScreen.objects.filter(
                mainscreen_id__mainscreen_name=module_name,
                is_active=True,
                is_deleted=False,
            ).values_list("userscreen_name", flat=True)
        )
        assert expected_screens <= actual_screens

    assert MainScreen.objects.count() == sum(map(len, EXPECTED_GROUPS.values()))

    legacy_type.refresh_from_db()
    assert legacy_type.is_active is False
    assert legacy_type.is_deleted is True
