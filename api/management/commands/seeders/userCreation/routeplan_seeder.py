from api.apps.routeplan import RoutePlan
from api.apps.district import District
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.staffUserType import StaffUserType
from api.apps.userCreation import User


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

        try:
            supervisor_role = StaffUserType.objects.get(name__iexact="supervisor")
        except StaffUserType.DoesNotExist:
            raise Exception("Supervisor role missing. Run StaffUserTypeSeeder first.")

        supervisors = User.objects.filter(
            staffusertype_id=supervisor_role,
            is_active=True,
            is_deleted=False,
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
            # Zones linked to district via unique_id
            district_zones = zones.filter(district_id=district.unique_id)

            if not district_zones.exists():
                continue

            for zone in district_zones:
                city_obj = zone.city_id  # FK object

                for vehicle in vehicles:
                    supervisor = supervisor_cycle[sup_index % sup_len]
                    sup_index += 1

                    defaults = {
                        "supervisor_id": supervisor,
                        "status": "ACTIVE",
                        "is_active": True,
                        "is_deleted": False,
                    }

                    qs = RoutePlan.objects.filter(
                        district_id=district,
                        city_id=city_obj,
                        zone_id=zone,
                        vehicle_id=vehicle,
                        is_deleted=False,
                    ).order_by("id")

                    existing = qs.first()

                    if existing:
                        for key, value in defaults.items():
                            setattr(existing, key, value)
                        existing.save(update_fields=list(defaults.keys()))
                        updated += 1
                    else:
                        RoutePlan.objects.create(
                            district_id=district,
                            city_id=city_obj,
                            zone_id=zone,
                            vehicle_id=vehicle,
                            **defaults,
                        )
                        created += 1

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------
        print(
            f"RoutePlan seeding completed | Created: {created}, Updated: {updated}"
        )
