"""Restrict `driver_user` (Blue Planet / Palakkad BP) to bin collection only.

Per the app's driver flow: a driver collects bins at collection points, full
stop. Household-door and bulk-waste pickup are handled by other crews (or a
future distinct role) — `driver_user` should never see household/bulk trips
on their home screen.

`driver_palakkad_trips.py` seeds three TripPlans (bin/household/bulk) sharing
`driver_user`'s StaffTemplate, since it was originally written to exercise
all three collection types end to end. This seeder narrows that back down
without deleting anything:

    1. Deactivate the household_collection and bulk_waste_collection
       TripPlans (`is_active=False`) so `generate_daily_trips` stops
       producing new assignments for them tomorrow onward.
    2. Cancel any already-generated household/bulk DailyTripAssignment rows
       for today (and any future date) so they disappear from
       `my-trips-today` immediately, without touching completed history.

Idempotent — safe to re-run.
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import Staffcreation


COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Palakkad BP"
DRIVER_USERNAME = "driver_user"

NON_BIN_TYPES = [
    TripPlan.COLLECTION_TYPE_HOUSEHOLD,
    TripPlan.COLLECTION_TYPE_BULK,
]


class DriverBinOnlySeeder(BaseSeeder):
    name = "driver_bin_only"

    def run(self):
        company = Company.objects.filter(name=COMPANY_NAME, is_deleted=False).first()
        project = Project.objects.filter(
            name=PROJECT_NAME, company_id=company, is_deleted=False
        ).first() if company else None
        driver = Staffcreation.objects.filter(
            username=DRIVER_USERNAME, is_deleted=False
        ).first()

        if not company or not project:
            self.log(f"'{PROJECT_NAME}' not found under '{COMPANY_NAME}' — nothing to restrict.")
            return
        if not driver:
            self.log(f"'{DRIVER_USERNAME}' not found — nothing to restrict.")
            return

        plans = TripPlan.objects.filter(
            company_id=company,
            project_id=project,
            staff_template_id__driver_id=driver,
            collection_type__in=NON_BIN_TYPES,
            is_deleted=False,
        )
        plan_count = plans.update(is_active=False, status=TripPlan.Status.INACTIVE)
        self.log(f"Deactivated {plan_count} household/bulk TripPlan(s) for {DRIVER_USERNAME}.")

        today = timezone.localdate()
        assignments = DailyTripAssignment.objects.filter(
            trip_plan_id__in=TripPlan.objects.filter(
                company_id=company,
                project_id=project,
                staff_template_id__driver_id=driver,
                collection_type__in=NON_BIN_TYPES,
            ),
            trip_date__gte=today,
            is_deleted=False,
        ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)

        cancelled = 0
        for assignment in assignments:
            if assignment.status == DailyTripAssignment.STATUS_COMPLETED:
                continue
            assignment.status = DailyTripAssignment.STATUS_CANCELLED
            assignment.save(update_fields=["status", "updated_at"])
            cancelled += 1
        self.log(
            f"Cancelled {cancelled} pending household/bulk DailyTripAssignment(s) "
            f"for {DRIVER_USERNAME} from {today} onward."
        )
        self.log(f"---{DRIVER_USERNAME} restricted to bin collection only---")
