"""Megha is the Blue Planet project admin, not a platform super admin: from
the Super Admin section she gets Staff Management only."""
import pytest

from app.management.commands.seeders.superadmin.screen_management.permissions import (
    PermissionSeeder,
)
from app.management.commands.seeders.superadmin.staff_management.gno_named_staff import (
    MeghaProjectAdminPermissionSeeder,
)
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.permission_catalog import SECTION_MODULES


def _granted_modules(staff):
    config = StaffAccessConfiguration.objects.get(staff_id=staff.staff_unique_id)
    main_ids = StaffAccessConfigurationPermission.objects.filter(
        staff_access_configuration_id=config.unique_id, is_deleted=False,
    ).values_list("mainscreen_id", flat=True)
    return set(
        MainScreen.objects.filter(unique_id__in=main_ids)
        .values_list("mainscreen_name", flat=True)
    )


@pytest.mark.django_db
def test_megha_gets_staff_management_but_no_platform_modules(company, project):
    staff = Staffcreation.objects.create(
        username="megha", employee_name="Megha",
        company_id=company.unique_id, project_id=project.unique_id,
    )
    PermissionSeeder().run()
    MeghaProjectAdminPermissionSeeder().run()

    modules = _granted_modules(staff)
    super_admin = set(SECTION_MODULES["super-admin"])
    assert modules & super_admin == {"staff-creations"}
    assert {"dashboard", "masters", "schedule-setup", "reports"} <= modules

    # A re-run removes super-admin grants she was given earlier.
    config = StaffAccessConfiguration.objects.get(staff_id=staff.staff_unique_id)
    company_main = MainScreen.objects.get(mainscreen_name="superadmin-masters")
    StaffAccessConfigurationPermission.objects.create(
        staff_access_configuration_id=config.unique_id,
        mainscreen_id=company_main.unique_id,
        userscreen_id="USERSCREEN-X",
        userscreenaction_id="USERSCRNACT-X",
    )
    MeghaProjectAdminPermissionSeeder().run()
    assert "superadmin-masters" not in _granted_modules(staff)
