from app.management.commands.seeders.base import BaseSeeder

# Common Masters
from app.models.common_masters.state import State

# Masters
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.panchayat import Panchayat
from app.models.assets.collection_point import Collection_point

# Super Admin
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


PANCHAYAT_CP_COORDS = [
    (13.151000, 80.201000),
    (13.152200, 80.202500),
    (13.153400, 80.203800),
    (13.154600, 80.205100),
    (13.155800, 80.206400),
]


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
        # WARD-BASED CP (legacy)
        # --------------------------------------------------
        ward_cp, ward_created = Collection_point.objects.update_or_create(
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

        # --------------------------------------------------
        # PANCHAYAT-BASED CPs FOR OPERATOR FLOW (5 CPs under Panchayat 1)
        # --------------------------------------------------
        panchayat_1 = Panchayat.objects.filter(
            panchayat_name="Panchayat 1",
            company_id=company,
            project_id=project,
        ).first()

        panchayat_created = 0
        if panchayat_1:
            for idx, (lat, lng) in enumerate(PANCHAYAT_CP_COORDS, start=1):
                cp_name = f"CP-PNY-{idx:02d}"
                _, created = Collection_point.objects.update_or_create(
                    cp_name=cp_name,
                    panchayat_id=panchayat_1,
                    company_id=company,
                    project_id=project,
                    defaults={
                        "state_id": tamil_nadu,
                        "district_id": chennai_dist,
                        "city_id": chennai_city,
                        "ward_id": None,
                        "latitude": lat,
                        "longitude": lng,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    panchayat_created += 1
        else:
            self.log("Panchayat 1 not found — skipping panchayat-based CPs.")

        action = "Created" if ward_created else "Updated"
        self.log(
            f"---Collection Points seeded | ward CP {action} | "
            f"panchayat CPs created={panchayat_created}---"
        )
