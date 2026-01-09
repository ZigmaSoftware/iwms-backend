from django.db import transaction

from api.apps.supervisor_zone_map import SupervisorZoneMap
from api.apps.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from api.apps.staffUserType import StaffUserType
from api.apps.userType import UserType
from api.apps.userCreation import User
from api.apps.zone import Zone


class SupervisorZoneMapSeeder:
    group = "user-creation"

    def run(self):
        print("Seeding Supervisor Zone Map...")

        staff_type = UserType.objects.get(name__iexact="staff")
        supervisor_role = StaffUserType.objects.get(
            name="supervisor",
            usertype_id=staff_type,
        )
        admin_role = StaffUserType.objects.get(
            name="admin",
            usertype_id=staff_type,
        )

        admin_user = User.objects.filter(
            staffusertype_id=admin_role,
            is_deleted=False,
            is_active=True,
        ).first()
        if not admin_user:
            raise Exception("Admin user missing. Run UserSeeder first.")

        supervisors = User.objects.filter(
            staffusertype_id=supervisor_role,
            is_deleted=False,
            is_active=True,
        ).select_related("staff_id")
        if not supervisors.exists():
            print("No supervisors found. Skipping supervisor zone map seeding.")
            return

        zones = list(
            Zone.objects.filter(is_active=True, is_deleted=False).select_related(
                "district_id",
                "city_id",
            ).order_by("name")
        )
        if not zones:
            print("No zones found. Skipping supervisor zone map seeding.")
            return

        grouped_zones = {}
        for zone in zones:
            district_uid = zone.district_id.unique_id
            city_uid = zone.city_id.unique_id
            grouped_zones.setdefault((district_uid, city_uid), []).append(zone)

        group_list = list(grouped_zones.items())
        if not group_list:
            print("No grouped zones found. Skipping supervisor zone map seeding.")
            return

        for index, supervisor in enumerate(supervisors, start=1):
            (district_uid, city_uid), zone_list = group_list[index % len(group_list)]
            zone_sample = zone_list[:2] if len(zone_list) > 1 else zone_list[:1]

            new_zone_ids = [zone.unique_id for zone in zone_sample if zone.unique_id]

            if not new_zone_ids:
                print(f"Skipping {supervisor.unique_id}: no valid zone IDs.")
                continue

            existing = SupervisorZoneMap.objects.filter(
                supervisor=supervisor,
                status="ACTIVE",
            ).first()

            old_zone_ids = existing.zone_ids if existing else None
            if existing and existing.zone_ids == new_zone_ids:
                continue

            with transaction.atomic():
                if existing:
                    existing.status = "INACTIVE"
                    existing.save(update_fields=["status"])

                SupervisorZoneMap.objects.create(
                    supervisor=supervisor,
                    district_id=district_uid,
                    city_id=city_uid,
                    zone_ids=new_zone_ids,
                    status="ACTIVE",
                )

                SupervisorZoneAccessAudit.objects.create(
                    supervisor=supervisor,
                    old_zone_ids=old_zone_ids,
                    new_zone_ids=new_zone_ids,
                    performed_by=admin_user,
                    performed_role="ADMIN",
                    remarks="Seeded supervisor zone access",
                )

        print("Supervisor Zone Map seeding completed.")
