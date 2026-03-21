from app.management.commands.seeders.base import BaseSeeder
from app.models.process.zone_property_load_tracker import ZonePropertyLoadTracker
from app.models.masters.zone import Zone
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class ZonePropertyLoadTrackerSeeder(BaseSeeder):
    name = "zone_property_load_tracker"

    def run(self):
        zones = list(Zone.objects.filter(is_active=True, is_deleted=False)[:2])
        vehicles = list(
            VehicleCreation.objects.filter(is_active=True, is_deleted=False)[:2]
        )
        property_obj = Property.objects.filter(is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(is_deleted=False).first()

        if not zones or not vehicles or not property_obj or not sub_property_obj:
            self.log("ZonePropertyLoadTrackerSeeder skipped (missing dependencies).")
            return

        created = 0
        for idx, zone in enumerate(zones):
            vehicle = vehicles[idx % len(vehicles)]
            _, was_created = ZonePropertyLoadTracker.objects.get_or_create(
                zone=zone,
                vehicle=vehicle,
                property=property_obj,
                sub_property=sub_property_obj,
                defaults={
                    "current_weight_kg": 100 + (idx * 50),
                },
            )
            if was_created:
                created += 1

        self.log(f"---Zone property load trackers seeded | Created: {created}---")
