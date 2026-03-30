# core/management/commands/seeders/vehicles/vehicle_creation.py
from datetime import date

from app.management.commands.seeders.base import BaseSeeder
from app.models.transport_masters.fuel import Fuel
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class VehicleCreationSeeder(BaseSeeder):
    name = "vehicle_creation"

    def _get_or_create_vehicle_type(self, vehicle_type, company, project):
        obj, created = VehicleTypeCreation.objects.get_or_create(
            vehicleType=vehicle_type,
            defaults={
                "description": f"{vehicle_type} vehicle type",
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

        return obj

    def _get_or_create_fuel(self, fuel_type):
        obj, created = Fuel.objects.get_or_create(
            fuel_type=fuel_type,
            defaults={
                "description": f"{fuel_type} fuel type",
                "is_active": True,
                "is_deleted": False,
            },
        )

        if not created and obj.is_deleted:
            obj.is_deleted = False
            obj.is_active = True
            obj.save(update_fields=["is_deleted", "is_active"])

        return obj

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

        vehicle_types = {
            "Compactor": self._get_or_create_vehicle_type("Compactor", company, project),
            "Tipping Truck": self._get_or_create_vehicle_type("Tipping Truck", company, project),
        }

        fuels = {
            "Diesel": self._get_or_create_fuel("Diesel"),
            "CNG": self._get_or_create_fuel("CNG"),
        }

        vehicles = [
            {
                "vehicle_no": "TN09AB1234",
                "vehicle_type": vehicle_types["Compactor"],
                "fuel_type": fuels["Diesel"],
                "capacity": "10.00",
                "mileage_per_liter": "6.50",
                "service_record": "Quarterly maintenance",
                "vehicle_insurance": "ICICI Lombard",
                "insurance_expiry_date": date(2026, 12, 31),
                "vehicle_condition": VehicleCreation.ConditionChoices.NEW,
                "fuel_tank_capacity": "150.00",
            },
            {
                "vehicle_no": "TN10CD5678",
                "vehicle_type": vehicle_types["Tipping Truck"],
                "fuel_type": fuels["CNG"],
                "capacity": "8.50",
                "mileage_per_liter": "7.25",
                "service_record": "Bi-annual maintenance",
                "vehicle_insurance": "Bajaj Allianz",
                "insurance_expiry_date": date(2026, 10, 15),
                "vehicle_condition": VehicleCreation.ConditionChoices.SECOND_HAND,
                "fuel_tank_capacity": "120.00",
            },
        ]

        for entry in vehicles:
            obj, created = VehicleCreation.objects.get_or_create(
                vehicle_no=entry["vehicle_no"],
                defaults={
                    "vehicle_type": entry["vehicle_type"],
                    "fuel_type": entry["fuel_type"],
                    "company_id": company,
                    "project_id": project,
                    "capacity": entry["capacity"],
                    "mileage_per_liter": entry["mileage_per_liter"],
                    "service_record": entry["service_record"],
                    "vehicle_insurance": entry["vehicle_insurance"],
                    "insurance_expiry_date": entry["insurance_expiry_date"],
                    "vehicle_condition": entry["vehicle_condition"],
                    "fuel_tank_capacity": entry["fuel_tank_capacity"],
                    "is_active": True,
                    "is_deleted": False,
                },
            )

            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log("---Vehicle creation seeded---")
