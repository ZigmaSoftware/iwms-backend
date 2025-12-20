# core/management/commands/seeders/assets/property.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.property import Property


class PropertySeeder(BaseSeeder):
    name = "property"

    def run(self):
        properties = [
            "Residential",
            "Commercial",
            "Industrial",
            "Institutional",
        ]

        for prop in properties:
            obj, created = Property.objects.get_or_create(
                property_name=prop,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                }
            )

            # Reactivate if soft-deleted
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log("Properties seeded")
