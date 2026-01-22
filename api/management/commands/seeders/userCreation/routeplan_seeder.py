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

        districts = District.objects.filter(is_deleted=False)
        zones = Zone.objects.filter(is_deleted=False)
        vehicles = VehicleCreation.objects.filter(
            is_deleted=False,
            is_active=True
        )

        supervisor_role = StaffUserType.objects.get(name__iexact="supervisor")
        supervisors = User.objects.filter(
            staffusertype_id=supervisor_role,
            is_active=True,
            is_deleted=False,
        )

        supervisor_cycle = list(supervisors)
        sup_len = len(supervisor_cycle)
        sup_index = 0

        created = 0
        updated = 0

        for district in districts:
            district_zones = zones.filter(district_id=district.unique_id)

            for zone in district_zones:
                city_obj = zone.city_id

                for vehicle in vehicles:
                    supervisor = supervisor_cycle[sup_index % sup_len]
                    sup_index += 1

                    qs = RoutePlan.objects.filter(
                        district_id=district,
                        city_id=city_obj,
                        zone_id=zone,
                        vehicle_id=vehicle,
                        is_deleted=False,
                    )

                    existing = qs.first()

                    if existing:
                        existing.supervisor_id = supervisor
                        existing.display_code = None  # regenerate
                        existing.save()
                        updated += 1
                    else:
                        RoutePlan.objects.create(
                            district_id=district,
                            city_id=city_obj,
                            zone_id=zone,
                            vehicle_id=vehicle,
                            supervisor_id=supervisor,
                            is_active=True,
                            is_deleted=False,
                        )
                        created += 1

        print(
            f"RoutePlan seeding completed | Created: {created}, Updated: {updated}"
        )
