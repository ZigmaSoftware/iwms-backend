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
        # A week of history (15 panchayat assignments per seeded date) gives
        # downstream seeders (BinCollectionEvent/WasteCollection/DailyTripLog)
        # enough source rows to show a realistic volume of data, while still
        # reserving today for RetripDemoSeeder's own hand-curated scenarios.
        date_range = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        for target_date in date_range:
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
            f"dates={date_range[0]}..{date_range[-1]} "
            f"created={totals['assignments_created']} "
            f"existing={totals['assignments_existing']} "
            f"collection_points={totals['collection_points_created']} "
            f"skipped={totals['skipped']} "
            f"errors={len(totals['errors'])}---"
        )

        for plan_id, error in totals["errors"][:5]:
            self.log(f"DailyTripAssignment seed error | plan={plan_id} | {error}")
