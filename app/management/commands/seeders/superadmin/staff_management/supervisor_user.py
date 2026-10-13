"""Ported from the government backend's SupervisorUserSeeder.

Creates a supervisor login (`supervisor_user` / `Supervisor123`) wired to
REAL data — not just a bare login — so the supervisor app module
(module5_supervisor) actually has something to show:

- `daily-trip-assignments/?mine=true` and `daily-trip-logs/?mine=true` scope
  to `TripPlan.supervisor_id == requester` (see the `mine` param added to
  DailyTripAssignmentViewSet / DailyTripLogViewSet), so this points
  driver_user's trip plan(s) today at the new supervisor.

Unlike government, this project has no GovernmentStaffUserType / "level"
concept and no `sync_staff_data_scope` (StaffDataScope) — tenancy here is
handled by CompanyScopedViewSet via company_id/project_id, which
`copy_flat_geo` + explicit company_id/project_id assignment below cover.

Must run AFTER the driver/operator demo seeders (AuthUserSeeder + the daily
trip assignment seeders) so driver_user has a trip today to attach to.
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.hierarchy import copy_flat_geo


class SupervisorUserSeeder(BaseSeeder):
    """Create a supervisor login that is responsible for driver_user's trip,
    so it shows up in the supervisor app."""

    name = "supervisor_user"

    USERNAME = "supervisor_user"
    PASSWORD = "Supervisor123"
    ROLE_NAME = "Company Supervisor"

    def run(self):
        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            self.log("UserType 'staff' missing — skipping.")
            return

        role, _ = StaffUserType.objects.get_or_create(
            name=self.ROLE_NAME,
            usertype_id=staff_type.unique_id if hasattr(staff_type, 'unique_id') else staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )

        driver = Staffcreation.objects.filter(
            username="driver_user", is_deleted=False
        ).first()
        if not driver:
            self.log("driver_user not found — run the staff-creations seed group first. Skipping.")
            return

        today = timezone.localdate()
        driver_id = driver.staff_unique_id if hasattr(driver, 'staff_unique_id') else driver
        template_ids = list(
            StaffTemplate.objects.filter(driver_id=driver_id, is_deleted=False)
            .values_list("unique_id", flat=True)
        )
        assignments = list(
            DailyTripAssignment.objects.filter(
                trip_date=today,
                is_deleted=False,
                staff_template_id__in=template_ids,
            )
        )
        if not assignments:
            self.log("driver_user has no trip today — run the daily-trip seeders first. Skipping.")
            return

        supervisor, created = Staffcreation.objects.get_or_create(
            username=self.USERNAME,
            defaults={
                "employee_name": "Supervisor User",
                "password": self.PASSWORD,
                "user_type_id": staff_type.unique_id if hasattr(staff_type, 'unique_id') else staff_type,
                "staffusertype_id": role.unique_id if hasattr(role, 'unique_id') else role,
                "company_id": driver.company_id,
                "project_id": driver.project_id,
                "is_active": True,
                "is_deleted": False,
                "is_superuser": False,
                "login_enabled": True,
                "approval_status": Staffcreation.APPROVAL_APPROVED,
            },
        )
        if not created:
            supervisor.employee_name = "Supervisor User"
            supervisor.password = self.PASSWORD
            supervisor.user_type_id = staff_type.unique_id if hasattr(staff_type, 'unique_id') else staff_type
            supervisor.staffusertype_id = role.unique_id if hasattr(role, 'unique_id') else role
            supervisor.company_id = driver.company_id
            supervisor.project_id = driver.project_id
            supervisor.is_active = True
            supervisor.is_deleted = False
            supervisor.is_superuser = False
            supervisor.login_enabled = True
            supervisor.approval_status = Staffcreation.APPROVAL_APPROVED

        copy_flat_geo(supervisor, assignments[0])
        supervisor.save()

        # Make this supervisor responsible for the trip plan(s) behind
        # driver_user's assignments today, so `?mine=true` surfaces them.
        supervisor_id = supervisor.staff_unique_id if hasattr(supervisor, 'staff_unique_id') else supervisor
        plan_ids = {a.trip_plan_id for a in assignments if a.trip_plan_id}
        updated = TripPlan.objects.filter(unique_id__in=plan_ids).update(
            supervisor_id=supervisor_id
        )

        self.log(
            f"{'Created' if created else 'Updated'} supervisor login: "
            f"{self.USERNAME} / {self.PASSWORD} — owns {updated} trip plan(s) "
            f"covering {len(assignments)} of driver_user's trips today."
        )
