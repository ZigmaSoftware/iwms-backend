from datetime import timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.services.daily_trip_generation import generate_daily_trips_for_date


class DailyTripAssignmentSeeder(BaseSeeder):
    name = "daily_trip_assignment"

    def run(self):
        today = timezone.localdate()
        totals = {
            "assignments_created": 0,
            "assignments_existing": 0,
            "collection_points_created": 0,
            "skipped": 0,
            "errors": [],
        }
        # Two dates yield 30 panchayat assignments (15 per seeded date),
        # enough source rows for both comparison dashboards.
        for target_date in (today - timedelta(days=1), today):
            result = generate_daily_trips_for_date(target_date, force=True)
            for key in (
                "assignments_created",
                "assignments_existing",
                "collection_points_created",
                "skipped",
            ):
                totals[key] += result[key]
            totals["errors"].extend(result["errors"])

        self.log(
            "---DailyTripAssignment seeded | "
            f"dates={today - timedelta(days=1)}..{today} "
            f"created={totals['assignments_created']} "
            f"existing={totals['assignments_existing']} "
            f"collection_points={totals['collection_points_created']} "
            f"skipped={totals['skipped']} "
            f"errors={len(totals['errors'])}---"
        )

        for plan_id, error in totals["errors"][:5]:
            self.log(f"DailyTripAssignment seed error | plan={plan_id} | {error}")
