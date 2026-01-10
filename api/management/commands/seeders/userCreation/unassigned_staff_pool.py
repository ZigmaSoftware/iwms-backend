from api.management.commands.seeders.base import BaseSeeder
from api.apps.unassigned_staff_pool import UnassignedStaffPool
from api.apps.userCreation import User
from api.apps.trip_instance import TripInstance
from api.apps.ward import Ward


class UnassignedStaffPoolSeeder(BaseSeeder):
    name = "unassigned_staff_pool"

    def run(self):
        staff_qs = User.objects.filter(
            staffusertype_id__name__in=["driver", "operator"],
            is_active=True,
            is_deleted=False,
        ).select_related("zone_id", "ward_id", "staffusertype_id")

        if not staff_qs.exists():
            self.log("UnassignedStaffPoolSeeder skipped (no staff users).")
            return

        active_instances = TripInstance.objects.filter(
            status__in=[
                TripInstance.Status.WAITING_FOR_LOAD,
                TripInstance.Status.READY,
                TripInstance.Status.IN_PROGRESS,
            ]
        ).select_related("staff_template", "zone")

        assigned_ids = set()
        latest_trip_per_zone = {}
        for instance in active_instances:
            staff_template = instance.staff_template
            if staff_template and staff_template.driver_id_id:
                assigned_ids.add(staff_template.driver_id_id)
            if staff_template and staff_template.operator_id_id:
                assigned_ids.add(staff_template.operator_id_id)
            latest_trip_per_zone.setdefault(instance.zone_id, instance)

        created = 0
        updated = 0

        for staff in staff_qs:
            if staff.unique_id in assigned_ids:
                UnassignedStaffPool.objects.filter(
                    operator_id=staff.unique_id
                ).update(status=UnassignedStaffPool.Status.ASSIGNED)
                UnassignedStaffPool.objects.filter(
                    driver_id=staff.unique_id
                ).update(status=UnassignedStaffPool.Status.ASSIGNED)
                continue

            zone = staff.zone_id
            if not zone:
                continue

            ward = staff.ward_id or Ward.objects.filter(
                zone_id=zone.unique_id
            ).first()
            if not ward:
                continue

            trip_instance = latest_trip_per_zone.get(zone.unique_id)
            payload = {
                "zone": zone,
                "ward": ward,
                "status": UnassignedStaffPool.Status.AVAILABLE,
                "trip_instance": trip_instance,
            }

            if staff.staffusertype_id and staff.staffusertype_id.name.lower() == "operator":
                _, was_created = UnassignedStaffPool.objects.update_or_create(
                    operator=staff,
                    zone=zone,
                    ward=ward,
                    defaults=payload,
                )
            else:
                _, was_created = UnassignedStaffPool.objects.update_or_create(
                    driver=staff,
                    zone=zone,
                    ward=ward,
                    defaults=payload,
                )

            if was_created:
                created += 1
            else:
                updated += 1

        self.log(f"Unassigned staff pool seeded | Created: {created}, Updated: {updated}")
