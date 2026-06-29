from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.services.daily_trip_generation import generate_daily_trips_for_date


class DailyTripAssignmentSeeder(BaseSeeder):
    name = "daily_trip_assignment"

    def run(self):
        today = timezone.localdate()
        result = generate_daily_trips_for_date(today, force=True)

        self.log(
            "---DailyTripAssignment seeded | "
            f"date={today} "
            f"created={result['assignments_created']} "
            f"existing={result['assignments_existing']} "
            f"collection_points={result['collection_points_created']} "
            f"skipped={result['skipped']} "
            f"errors={len(result['errors'])}---"
        )

        for plan_id, error in result["errors"][:5]:
            self.log(f"DailyTripAssignment seed error | plan={plan_id} | {error}")
