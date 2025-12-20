# core/management/commands/seeders/assets/fuel.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.fuel import Fuel


class FuelSeeder(BaseSeeder):
    name = "fuel"

    def run(self):
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

        self.log("Fuel types seeded")
