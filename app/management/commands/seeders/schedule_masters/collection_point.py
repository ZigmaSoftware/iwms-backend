from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.state import State
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.collection_point import Collection_point
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


# 14 panchayat CPs spread across 3 panchayats + 1 ward CP = 15 total
PANCHAYAT_CP_COORDS = {
    "Panchayat 1": [
        (13.151000, 80.201000),
        (13.152200, 80.202500),
        (13.153400, 80.203800),
        (13.154600, 80.205100),
        (13.155800, 80.206400),
    ],
    "Panchayat 2": [
        (13.161000, 80.211000),
        (13.162200, 80.212500),
        (13.163400, 80.213800),
        (13.164600, 80.215100),
        (13.165800, 80.216400),
    ],
    "Panchayat 3": [
        (13.171000, 80.221000),
        (13.172200, 80.222500),
        (13.173400, 80.223800),
        (13.174600, 80.225100),
    ],
}


class CollectionPointSeeder(BaseSeeder):
    name = "collection_point"

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        ward_1 = Ward.objects.get(
            ward_name="Ward 1",
            city_id=chennai_city,
            company_id=company,
            project_id=project,
        )

        # Ward-based CP (1 record)
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

        # Panchayat-based CPs (14 records across 3 panchayats)
        panchayat_created = 0
        for panchayat_name, coords in PANCHAYAT_CP_COORDS.items():
            panchayat = Panchayat.objects.filter(
                panchayat_name=panchayat_name,
                company_id=company,
                project_id=project,
            ).first()
            if not panchayat:
                self.log(f"{panchayat_name} not found — skipping.")
                continue

            panchayat_prefix = panchayat_name.replace(" ", "").upper()[:3]
            for idx, (lat, lng) in enumerate(coords, start=1):
                cp_name = f"CP-{panchayat_prefix}-{idx:02d}"
                _, created = Collection_point.objects.update_or_create(
                    cp_name=cp_name,
                    panchayat_id=panchayat,
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

        action = "Created" if ward_created else "Updated"
        self.log(
            f"---Collection Points seeded | ward CP {action} | "
            f"panchayat CPs created={panchayat_created} | total=15---"
        )
