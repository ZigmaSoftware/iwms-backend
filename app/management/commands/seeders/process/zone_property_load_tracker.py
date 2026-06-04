from app.management.commands.seeders.base import BaseSeeder
from app.models.process.zone_property_load_tracker import ZonePropertyLoadTracker
from app.models.masters.zone import Zone
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class ZonePropertyLoadTrackerSeeder(BaseSeeder):
    name = "zone_property_load_tracker"

    def run(self):
        zones = list(Zone.objects.filter(is_active=True, is_deleted=False).order_by("zone_name")[:15])
        vehicles = list(VehicleCreation.objects.filter(is_active=True, is_deleted=False).order_by("created_at"))
        properties = list(Property.objects.filter(is_deleted=False))
        sub_properties = list(SubProperty.objects.filter(is_deleted=False))

        if not zones or not vehicles or not properties or not sub_properties:
            self.log("ZonePropertyLoadTrackerSeeder skipped (missing dependencies).")
            return

        created = 0
        for idx, zone in enumerate(zones):
            vehicle = vehicles[idx % len(vehicles)]
            property_obj = properties[idx % len(properties)]
            sub_property_obj = sub_properties[idx % len(sub_properties)]

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

        self.log(f"---Zone property load trackers seeded | created={created} | total={len(zones)}---")
