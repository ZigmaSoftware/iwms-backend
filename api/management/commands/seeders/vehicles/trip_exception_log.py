from api.management.commands.seeders.base import BaseSeeder
from api.apps.trip_exception_log import TripExceptionLog
from api.apps.trip_instance import TripInstance


class TripExceptionLogSeeder(BaseSeeder):
    name = "trip_exception_log"

    def run(self):
        trip = TripInstance.objects.order_by("-created_at").first()
        if not trip:
            self.log("TripExceptionLogSeeder skipped (no trip instances).")
            return

        if trip.status in [TripInstance.Status.COMPLETED, TripInstance.Status.CANCELLED]:
            self.log("TripExceptionLogSeeder skipped (trip is inactive).")
            return

        existing = TripExceptionLog.objects.filter(
            trip_instance=trip,
            exception_type=TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
        )
        if existing.exists():
            self.log("Trip exception log already exists; skipping create.")
            return

        TripExceptionLog.objects.create(
            trip_instance=trip,
            exception_type=TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
            remarks="Seeder: missed attendance in last window",
            detected_by=TripExceptionLog.DetectedBy.SYSTEM,
        )

        self.log("Trip exception log seeded")
