# core/management/commands/seeders/assets/fuel.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.transport_masters.fuel import Fuel
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class FuelSeeder(BaseSeeder):
    name = "fuel"

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

        fuels = [
            {
                "fuel_type": "Petrol",
                "description": "Petroleum-based fuel for light vehicles",
            },
            {
                "fuel_type": "Diesel",
                "description": "High-efficiency fuel for heavy vehicles",
            },
            {
                "fuel_type": "CNG",
                "description": "Compressed Natural Gas",
            },
            {
                "fuel_type": "Electric",
                "description": "Electric-powered vehicles",
            },
        ]

        for fuel in fuels:
            obj, created = Fuel.objects.get_or_create(
                fuel_type=fuel["fuel_type"],
                defaults={
                    "description": fuel["description"],
                    "is_active": True,
                    "is_deleted": False,
                }
            )

            # Reactivate if soft-deleted
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log("---Fuel types seeded---")
