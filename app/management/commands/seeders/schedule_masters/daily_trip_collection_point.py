from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.services.daily_trip_generation import ensure_assignment_collection_points


class DailyTripCollectionPointSeeder(BaseSeeder):
    name = "daily_trip_collection_point"

    def run(self):
        today = timezone.localdate()
        assignments = (
            DailyTripAssignment.objects
            .filter(trip_date=today, is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related("trip_plan_id")
        )

        if not assignments.exists():
            assignments = (
                DailyTripAssignment.objects
                .filter(is_deleted=False)
                .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
                .select_related("trip_plan_id")
                .order_by("-trip_date", "-scheduled_time")[:10]
            )

        if not assignments:
            self.log("No DailyTripAssignment found — skipping.")
            return

        total_created = 0
        for assignment in assignments:
            total_created += ensure_assignment_collection_points(assignment)

        self.log(
            f"---DailyTripCollectionPoint seeded | created={total_created}---"
        )
