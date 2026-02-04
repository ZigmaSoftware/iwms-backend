from datetime import datetime, timedelta

from django.utils import timezone

from api.management.commands.seeders.base import BaseSeeder
from api.models.vehicles.bin_load_log import BinLoadLog
from api.models.masters.zone import Zone
from api.models.vehicles.vehicleCreation import VehicleCreation
from api.models.assets.property import Property
from api.models.assets.subproperty import SubProperty
from api.models.masters.bin import Bin


class BinLoadLogSeeder(BaseSeeder):
    name = "bin_load_log"

    def run(self):
        zones = list(Zone.objects.filter(is_active=True, is_deleted=False)[:2])
        vehicles = list(
            VehicleCreation.objects.filter(is_active=True, is_deleted=False)[:2]
        )
        property_obj = Property.objects.filter(is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(is_deleted=False).first()
        bins = list(Bin.objects.filter(is_active=True, is_deleted=False)[:2])

        if not zones or not vehicles or not property_obj or not sub_property_obj:
            self.log("BinLoadLogSeeder skipped (missing dependencies).")
            return

        start_time = timezone.make_aware(datetime(2026, 1, 1, 6, 0, 0))
        created = 0

        for idx, zone in enumerate(zones):
            vehicle = vehicles[idx % len(vehicles)]
            bin_obj = bins[idx % len(bins)] if bins else None
            event_time = start_time + timedelta(minutes=15 * idx)

            _, was_created = BinLoadLog.objects.get_or_create(
                zone=zone,
                vehicle=vehicle,
                property=property_obj,
                sub_property=sub_property_obj,
                event_time=event_time,
                defaults={
                    "weight_kg": 250 + (idx * 50),
                    "source_type": BinLoadLog.SourceType.MANUAL,
                    "processed": False,
                    "bin": bin_obj,
                },
            )

            if was_created:
                created += 1

        self.log(f"Bin load logs seeded | Created: {created}")
