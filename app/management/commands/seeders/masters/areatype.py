from app.management.commands.seeders.base import BaseSeeder

# Common Masters
from app.models.common_masters.state import State

# Masters
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.areatype import AreaType

# Super Admin
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class AreaTypeSeeder(BaseSeeder):
    name = "areatype"

    def run(self):

        # --------------------------------------------------
        # COMPANY & PROJECT
        # --------------------------------------------------
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        # --------------------------------------------------
        # LOCATION DATA
        # --------------------------------------------------
        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        # --------------------------------------------------
        # CREATE URBAN AREA TYPE
        # --------------------------------------------------
        urban, created_urban = AreaType.objects.update_or_create(
            name="Urban",
            defaults={
                "state_id": tamil_nadu,
                "district_id": chennai_dist,
                "city_id": chennai_city,
                "company_id": company,
                "project_id": project,
                "description": "Urban Area",
                "is_active": True,
                "is_deleted": False,
            },
        )

        action1 = "Created" if created_urban else "Updated"
        self.log(f"---AreaType seeded: {urban.name} ({action1})---")

        # --------------------------------------------------
        # CREATE RURAL AREA TYPE
        # --------------------------------------------------
        rural, created_rural = AreaType.objects.update_or_create(
            name="Rural",
            defaults={
                "state_id": tamil_nadu,
                "district_id": chennai_dist,
                "city_id": chennai_city,
                "company_id": company,
                "project_id": project,
                "description": "Rural Area",
                "is_active": True,
                "is_deleted": False,
            },
        )

        action2 = "Created" if created_rural else "Updated"
        self.log(f"---AreaType seeded: {rural.name} ({action2})---")