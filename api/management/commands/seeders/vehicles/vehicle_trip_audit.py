from datetime import timedelta

from django.utils import timezone

from api.management.commands.seeders.base import BaseSeeder
from api.apps.trip_instance import TripInstance
from api.apps.vehicle_trip_audit import VehicleTripAudit


class VehicleTripAuditSeeder(BaseSeeder):
    name = "vehicle_trip_audit"

    def run(self):
        trip = TripInstance.objects.order_by("-created_at").first()
        if not trip:
            self.log("VehicleTripAuditSeeder skipped (no trip instances).")
            return

        if trip.status != TripInstance.Status.IN_PROGRESS:
            trip.status = TripInstance.Status.IN_PROGRESS
            trip.save(update_fields=["status"])

        captured_at = timezone.now() - timedelta(minutes=1)
        gps_lat = [
            "13.0826800",
            "13.0826810",
            "13.0826820",
            "13.0826830",
            "13.0826840",
            "13.0826850",
            "13.0826860",
            "13.0826870",
            "13.0826880",
            "13.0826890",
            "13.0826900",
            "13.0826910",
        ]
        gps_lon = [
            "80.2707180",
            "80.2707190",
            "80.2707200",
            "80.2707210",
            "80.2707220",
            "80.2707230",
            "80.2707240",
            "80.2707250",
            "80.2707260",
            "80.2707270",
            "80.2707280",
            "80.2707290",
        ]

        _, created = VehicleTripAudit.objects.get_or_create(
            trip_instance=trip,
            vehicle=trip.vehicle,
            captured_at=captured_at,
            defaults={
                "gps_lat": gps_lat,
                "gps_lon": gps_lon,
                "avg_speed": "2.50",
            },
        )

        if created:
            self.log("Vehicle trip audit seeded")
        else:
            self.log("VehicleTripAuditSeeder skipped (already seeded)")
