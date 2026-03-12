from app.management.commands.seeders.base import BaseSeeder

# Common Masters
from app.models.common_masters.state import State

# Masters
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.assets.collection_point import Collection_point

# Super Admin
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class CollectionPointSeeder(BaseSeeder):
    name = "collection_point"

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

        ward_1 = Ward.objects.get(
            ward_name="Ward 1",
            city_id=chennai_city,
            company_id=company,
            project_id=project,
        )

        # --------------------------------------------------
        # CREATE COLLECTION POINT (Ward Based)
        # --------------------------------------------------
        cp, created = Collection_point.objects.update_or_create(
            cp_name="CP 1",
            ward_id=ward_1,
            company_id=company,
            project_id=project,
            defaults={
                "state_id": tamil_nadu,
                "district_id": chennai_dist,
                "city_id": chennai_city,
                "latitude": 13.083000,
                "longitude": 80.271000,
                "is_active": True,
                "is_deleted": False,
            },
        )

        action = "Created" if created else "Updated"
        self.log(f"---Collection Point seeded: {cp.cp_name} ({action})---")