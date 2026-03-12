from app.management.commands.seeders.base import BaseSeeder

from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy


class AdministrativeHierarchySeeder(BaseSeeder):
    name = "hierarchy"

    def run(self):

        # --------------------------------------------------
        # GET AREA TYPES
        # --------------------------------------------------
        urban = AreaType.objects.get(name="Urban")
        rural = AreaType.objects.get(name="Rural")

        # --------------------------------------------------
        # URBAN HIERARCHY
        # --------------------------------------------------
        urban_levels = ["Zone", "Ward"]

        for level in urban_levels:
            obj, created = AdministrativeHierarchy.objects.get_or_create(
                area_type=urban,
                level_name=level,
            )

            action = "Created" if created else "Exists"
            self.log(f"---Hierarchy seeded: {urban.name} - {level} ({action})---")

        # --------------------------------------------------
        # RURAL HIERARCHY
        # --------------------------------------------------
        rural_levels = ["Panchayat"]

        for level in rural_levels:
            obj, created = AdministrativeHierarchy.objects.get_or_create(
                area_type=rural,
                level_name=level,
            )

            action = "Created" if created else "Exists"
            self.log(f"---Hierarchy seeded: {rural.name} - {level} ({action})---")