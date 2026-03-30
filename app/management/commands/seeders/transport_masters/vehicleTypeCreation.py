from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation


class VehicleTypeCreationSeeder(BaseSeeder):
    name = "vehicle_type_creation"

    def run(self):
        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={
                "description": "Integrated Waste Management System",
                "is_active": True,
                "is_deleted": False,
            },
        )
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

        vehicle_types = [
            {
                "vehicleType": "Compactor",
                "description": "Compactor vehicle type",
            },
            {
                "vehicleType": "Tipping Truck",
                "description": "Tipping truck vehicle type",
            },
        ]

        for entry in vehicle_types:
            obj, created = VehicleTypeCreation.objects.get_or_create(
                vehicleType=entry["vehicleType"],
                defaults={
                    "description": entry["description"],
                    "company_id": company,
                    "project_id": project,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

            if not created:
                update_fields = []
                if obj.is_deleted:
                    obj.is_deleted = False
                    update_fields.append("is_deleted")
                if not obj.is_active:
                    obj.is_active = True
                    update_fields.append("is_active")
                if obj.company_id_id != company.unique_id:
                    obj.company_id = company
                    update_fields.append("company_id")
                if obj.project_id_id != project.unique_id:
                    obj.project_id = project
                    update_fields.append("project_id")
                if update_fields:
                    obj.save(update_fields=update_fields)

        self.log("---Vehicle types seeded---")
