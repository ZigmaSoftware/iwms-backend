from datetime import timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.audits.vehicle_trip_audit import VehicleTripAudit


class VehicleTripAuditSeeder(BaseSeeder):
    name = "vehicle_trip_audit"

    def run(self):
        trips = list(
            DailyTripAssignment.objects.exclude(
                status=DailyTripAssignment.STATUS_CANCELLED
            ).order_by("-created_at")[:15]
        )

        if not trips:
            self.log("VehicleTripAuditSeeder skipped (no daily trip assignments).")
            return

        # Mark trips in-progress so the audit is valid
        for trip in trips:
            if trip.status != DailyTripAssignment.STATUS_IN_PROGRESS:
                trip.status = DailyTripAssignment.STATUS_IN_PROGRESS
                trip.save(update_fields=["status"])

        created = 0
        now = timezone.now()

        for idx, trip in enumerate(trips):
            if not trip.vehicle_id:
                continue

            captured_at = now - timedelta(minutes=1 + idx * 5)

            # Slight lat/lon variation per trip
            base_lat = 13.0826800 + (idx * 0.0001)
            base_lon = 80.2707180 + (idx * 0.0001)
            gps_lat = [f"{base_lat + j * 0.00001:.7f}" for j in range(12)]
            gps_lon = [f"{base_lon + j * 0.00001:.7f}" for j in range(12)]

            _, was_created = VehicleTripAudit.objects.get_or_create(
                daily_trip_assignment=trip,
                vehicle=trip.vehicle_id,
                captured_at=captured_at,
                defaults={
                    "gps_lat": gps_lat,
                    "gps_lon": gps_lon,
                    "avg_speed": f"{2.50 + idx * 0.10:.2f}",
                },
            )
            if was_created:
                created += 1

        self.log(f"---Vehicle trip audits seeded | created={created} | total_trips={len(trips)}---")
