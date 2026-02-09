from app.models.process.routeplan import RoutePlan
from app.models.masters.district import District
from app.models.masters.zone import Zone
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.user_creations.staffcreation import StaffOfficeDetails
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


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
        supervisors = StaffOfficeDetails.objects.filter(
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
                    company = getattr(supervisor, "company_id", None) or getattr(vehicle, "company_id", None)
                    project = getattr(supervisor, "project_id", None) or getattr(vehicle, "project_id", None)
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
                        if not getattr(existing, "company_id", None):
                            existing.company_id = company
                        if not getattr(existing, "project_id", None):
                            existing.project_id = project
                        existing.save()
                        updated += 1
                    else:
                        RoutePlan.objects.create(
                            district_id=district,
                            city_id=city_obj,
                            zone_id=zone,
                            vehicle_id=vehicle,
                            supervisor_id=supervisor,
                            company_id=company,
                            project_id=project,
                            is_active=True,
                            is_deleted=False,
                        )
                        created += 1

        print(
            f"---RoutePlan seeding completed | Created: {created}, Updated: {updated}---"
        )
