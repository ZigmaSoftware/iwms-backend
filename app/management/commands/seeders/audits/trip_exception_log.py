from app.management.commands.seeders.base import BaseSeeder
from app.models.audits.trip_exception_log import TripExceptionLog
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment


class TripExceptionLogSeeder(BaseSeeder):
    name = "trip_exception_log"

    # Cycle through available exception types
    EXCEPTION_TYPES = [
        TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
        TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
        TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
        TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
        TripExceptionLog.ExceptionType.MISSED_ATTENDANCE,
    ]

    def run(self):
        trips = list(
            DailyTripAssignment.objects.exclude(
                status__in=[
                    DailyTripAssignment.STATUS_COMPLETED,
                    DailyTripAssignment.STATUS_CANCELLED,
                ]
            ).order_by("-created_at")[:15]
        )

        if not trips:
            self.log("TripExceptionLogSeeder skipped (no active daily trip assignments).")
            return

        exception_types = list(TripExceptionLog.ExceptionType)
        created = 0

        for idx, trip in enumerate(trips):
            exception_type = exception_types[idx % len(exception_types)]

            existing = TripExceptionLog.objects.filter(
                daily_trip_assignment=trip,
                exception_type=exception_type,
            ).exists()
            if existing:
                continue

            TripExceptionLog.objects.create(
                daily_trip_assignment=trip,
                exception_type=exception_type,
                remarks=f"Seeder log #{idx + 1}: {exception_type}",
                detected_by=TripExceptionLog.DetectedBy.SYSTEM,
            )
            created += 1

        self.log(f"---Trip exception logs seeded | created={created} | total_trips={len(trips)}---")
