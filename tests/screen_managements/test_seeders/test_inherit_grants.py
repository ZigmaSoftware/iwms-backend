import pytest

from app.management.commands.seeders.superadmin.screen_management.permissions import (
    PermissionSeeder,
)
from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfigurationPermission,
)
from app.utils.permission_catalog import INHERITS_GRANTS_FROM


def test_daily_trip_tracking_inherits_the_collection_point_grants():
    assert INHERITS_GRANTS_FROM["daily-trip-tracking"] == "daily-trip-collection-points"


@pytest.mark.django_db
def test_split_screen_copies_company_and_staff_grants_once():
    source = UserScreen.objects.create(
        userscreen_name="daily-trip-collection-points",
        mainscreen_id="MAIN-OPS", folder_name="x", icon_name="x", order_no=1,
    )
    target = UserScreen.objects.create(
        userscreen_name="daily-trip-tracking",
        mainscreen_id="MAIN-OPS", folder_name="y", icon_name="y", order_no=2,
    )
    for action in ("ACT-VIEW", "ACT-EDIT"):
        CompanyUserScreenPermission.objects.create(
            company_id="CMP-1", project_id="PRJ-1", mainscreen_id="MAIN-OPS",
            userscreen_id=source.unique_id, userscreenaction_id=action,
            order_no=1, description="view daily-trip-collection-points",
        )
    StaffAccessConfigurationPermission.objects.create(
        staff_access_configuration_id="SAC-1", mainscreen_id="MAIN-OPS",
        userscreen_id=source.unique_id, userscreenaction_id="ACT-VIEW",
    )

    seeder = PermissionSeeder()
    seeder._inherit_grants(target, "daily-trip-collection-points")
    seeder._inherit_grants(target, "daily-trip-collection-points")  # idempotent

    company = CompanyUserScreenPermission.objects.filter(userscreen_id=target.unique_id)
    assert sorted(company.values_list("userscreenaction_id", flat=True)) == ["ACT-EDIT", "ACT-VIEW"]
    assert set(company.values_list("company_id", "project_id")) == {("CMP-1", "PRJ-1")}
    assert company.first().description == "view daily-trip-tracking"

    staff = StaffAccessConfigurationPermission.objects.filter(userscreen_id=target.unique_id)
    assert list(staff.values_list("staff_access_configuration_id", "userscreenaction_id")) == [
        ("SAC-1", "ACT-VIEW")
    ]
    # The source keeps its own grants.
    assert CompanyUserScreenPermission.objects.filter(userscreen_id=source.unique_id).count() == 2
