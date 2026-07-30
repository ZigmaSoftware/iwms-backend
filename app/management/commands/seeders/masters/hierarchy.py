from app.management.commands.seeders.base import BaseSeeder

from app.models.masters.hierarchy import AdministrativeHierarchy


class AdministrativeHierarchySeeder(BaseSeeder):
    name = "hierarchy"

    HIERARCHY_STRUCTURE = [
        "Zone",
        "Ward",
        "Block",
        "Street",
        "Block Panchayat Union",
        "Panchayat",
        "Village",
        "Hamlet",
        "Division",
        "Sector",
        "Estate",
        "Phase",
        "Complex",
        "Market",
        "Bay",
        "Harbor",
    ]

    def run(self):
        for level_name in self.HIERARCHY_STRUCTURE:
            obj, created = AdministrativeHierarchy.objects.get_or_create(
                level_name=level_name,
            )
            action = "Created" if created else "Exists"
            self.log(f"Hierarchy seeded: {level_name} ({action})")

        self.log(f"---Hierarchies seeded ({len(self.HIERARCHY_STRUCTURE)} records)---")
