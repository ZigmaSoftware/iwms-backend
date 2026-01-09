from api.apps.routeplan import RoutePlan

from api.apps.district import District
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.staffcreation import StaffOfficeDetails


class RoutePlanSeeder:
    group = "route-plan"

    def run(self):
        print("Seeding Route Plans...")

        # --------------------------------------------------
        # VALIDATE DEPENDENCIES
        # --------------------------------------------------
        districts = District.objects.filter(is_deleted=False)
        zones = Zone.objects.filter(is_deleted=False)
        vehicles = VehicleCreation.objects.filter(is_deleted=False, is_active=True)
        supervisors = StaffOfficeDetails.objects.filter(
            designation__iexact="supervisor",
            active_status=True
        )

        if not districts.exists():
            raise Exception("District master missing. Run masters seeder first.")

        if not zones.exists():
            raise Exception("Zone master missing. Run masters seeder first.")

        if not vehicles.exists():
            raise Exception("No active vehicles found. Seed vehicles first.")

        if not supervisors.exists():
            raise Exception("No supervisors found. Seed staff first.")

        # --------------------------------------------------
        # SEED LOGIC (CONTROLLED, NON-EXPLOSIVE)
        # --------------------------------------------------
        supervisor_cycle = list(supervisors)
        sup_len = len(supervisor_cycle)
        sup_index = 0

        created = 0
        updated = 0

        for district in districts:
            # District uses `unique_id` as primary key
            district_zones = zones.filter(district_id=district.unique_id)

            if not district_zones.exists():
                continue

            for zone in district_zones:
                # Vehicles are not associated with zones currently; use all active vehicles
                zone_vehicles = vehicles

                for vehicle in zone_vehicles:
                    supervisor = supervisor_cycle[sup_index % sup_len]
                    sup_index += 1

                    defaults = {
                        "supervisor_id": supervisor.id,
                        "status": "ACTIVE",
                        "is_active": True,
                        "is_deleted": False,
                    }

                    qs = RoutePlan.objects.filter(
                        district_id=district.unique_id,
                        zone_id=zone.unique_id,
                        vehicle_id=vehicle.id,
                    ).order_by("id")

                    existing = qs.first()
                    if existing:
                        for key, value in defaults.items():
                            setattr(existing, key, value)
                        existing.save(update_fields=list(defaults.keys()))
                        updated += 1
                    else:
                        RoutePlan.objects.create(
                            district_id=district.unique_id,
                            zone_id=zone.unique_id,
                            vehicle_id=vehicle.id,
                            **defaults,
                        )
                        created += 1

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------
        print(f"RoutePlan seeding completed | Created: {created}, Updated: {updated}")
