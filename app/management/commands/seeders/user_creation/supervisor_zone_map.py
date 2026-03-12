from django.db import transaction

from app.models.user_creations.supervisor_zone_map import SupervisorZoneMap
from app.models.audits.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.user_creations.staffcreation import Staffcreation
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


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

        admin_user = Staffcreation.objects.filter(
            staffusertype_id=admin_role,
            is_deleted=False,
            is_active=True,
        ).first()
        if not admin_user:
            raise Exception("Admin staff missing. Run StaffSeeder first.")

        supervisors = Staffcreation.objects.filter(
            staffusertype_id=supervisor_role,
            is_deleted=False,
            is_active=True,
        )
        if not supervisors.exists():
            print("No supervisors found. Skipping supervisor zone map seeding.")
            return

        zones = list(
            Zone.objects.filter(is_active=True, is_deleted=False).select_related(
                "district_id",
                "city_id",
            ).order_by("zone_name")
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

            district_obj = zone_list[0].district_id if zone_list else None
            city_obj = zone_list[0].city_id if zone_list else None

            if not new_zone_ids:
                print(f"Skipping {supervisor.staff_unique_id}: no valid zone IDs.")
                continue
            company = getattr(supervisor, "company_id", None) or getattr(admin_user, "company_id", None)
            project = getattr(supervisor, "project_id", None) or getattr(admin_user, "project_id", None)
            if not company:
                company, _ = Company.objects.get_or_create(
                    name="IWMS",
                    defaults={
                        "description": "Integrated Waste Management System",
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
            if not project:
                project_name = f"{company.name} Main Project"
                project, _ = Project.objects.get_or_create(
                    name=project_name,
                    company_id=company,
                    defaults={
                        "description": f"Default project for {company.name}",
                        "is_active": True,
                        "is_deleted": False,
                    },
                )

            existing = SupervisorZoneMap.objects.filter(
                supervisor_id=supervisor,
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
                    supervisor_id=supervisor,
                    district_id=district_obj,
                    city_id=city_obj,
                    company_id=company,
                    project_id=project,
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
                    company_id=company,
                    project_id=project,
                )

        print("---Supervisor Zone Map seeding completed.---")
