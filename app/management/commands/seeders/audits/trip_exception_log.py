from app.management.commands.seeders.base import BaseSeeder
from app.models.audits.trip_exception_log import TripExceptionLog
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment


class TripExceptionLogSeeder(BaseSeeder):
    name = "trip_exception_log"

    def run(self):
        trip = DailyTripAssignment.objects.order_by("-created_at").first()
        if not trip:
            self.log("TripExceptionLogSeeder skipped (no daily trip assignments).")
            return

        if trip.status in [DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED]:
            self.log("TripExceptionLogSeeder skipped (trip is inactive).")
            return

        existing = TripExceptionLog.objects.filter(
            daily_trip_assignment=trip,
            exception_type=TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
        )
        if existing.exists():
            self.log("Trip exception log already exists; skipping create.")
            return

        TripExceptionLog.objects.create(
            daily_trip_assignment=trip,
            exception_type=TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
            remarks="Seeder: missed attendance in last window",
            detected_by=TripExceptionLog.DetectedBy.SYSTEM,
        )

        self.log("---Trip exception log seeded---")
