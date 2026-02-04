# core/management/commands/seeders/assets/subproperty.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.property import Property
from app.models.assets.subproperty import SubProperty

class SubPropertySeeder(BaseSeeder):
    name = "sub_property"

    def run(self):
        property_map = {
            "Residential": [
                "Apartment",
                "Individual House",
                "Villa",
            ],
            "Commercial": [
                "Office",
                "Shop",
                "Mall",
            ],
            "Industrial": [
                "Factory",
                "Warehouse",
            ],
        }

        for property_name, subproperties in property_map.items():
            property_obj = Property.objects.get(property_name=property_name)

            for sub_name in subproperties:
                obj, created = SubProperty.objects.get_or_create(
                    property_id=property_obj,
                    sub_property_name=sub_name,
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

        self.log("---Sub-properties seeded---")
