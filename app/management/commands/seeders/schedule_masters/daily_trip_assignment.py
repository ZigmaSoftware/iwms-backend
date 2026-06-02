from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.trip_plan import TripPlan


class DailyTripAssignmentSeeder(BaseSeeder):
    name = "daily_trip_assignment"

    def run(self):
        today = timezone.localdate()
        plans = TripPlan.objects.filter(
            is_deleted=False,
            status=TripPlan.Status.ACTIVE,
            approval_status=TripPlan.ApprovalStatus.APPROVED,
        )

        if not plans.exists():
            self.log("No active approved TripPlan found — aborting.")
            return

        created_count = 0
        for plan in plans:
            existing = DailyTripAssignment.objects.filter(
                trip_plan_id=plan,
                trip_date=today,
                scheduled_time=plan.scheduled_time,
                is_deleted=False,
            ).first()
            if existing:
                continue

            DailyTripAssignment.objects.create(
                company_id=plan.company_id,
                project_id=plan.project_id,
                trip_plan_id=plan,
                staff_template_id=plan.staff_template_id,
                panchayat_id=plan.panchayat_id,
                ward_id=plan.ward_id,
                waste_type_id=plan.waste_type_id,
                vehicle_id=plan.vehicle_id,
                trip_date=today,
                scheduled_time=plan.scheduled_time,
                status=DailyTripAssignment.STATUS_SCHEDULED,
                approval_status=DailyTripAssignment.APPROVAL_APPROVED,
            )
            created_count += 1

        self.log(f"---DailyTripAssignment seeded | created={created_count}---")
