from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.state import State
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.collection_point import Collection_point
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class CollectionPointSeeder(BaseSeeder):
    name = "collection_point"
    POINTS_PER_AREA = 3

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        # --- Ward-based CPs (multiple per ward) ---
        wards = list(
            Ward.objects.filter(
                company_id=company, project_id=project, is_deleted=False
            ).order_by("ward_name")
        )
        ward_created = 0
        for idx, ward in enumerate(wards, start=1):
            base_lat = float(ward.latitude) if ward.latitude else 13.0840
            base_lon = float(ward.longitude) if ward.longitude else 80.2720
            for stop_no in range(1, self.POINTS_PER_AREA + 1):
                cp_name = f"CP-WARD-{idx:02d}-{stop_no:02d}"
                offset = 0.0005 * stop_no
                _, created = Collection_point.objects.update_or_create(
                    cp_name=cp_name,
                    ward_id=ward,
                    company_id=company,
                    project_id=project,
                    defaults={
                        "state_id": tamil_nadu,
                        "district_id": chennai_dist,
                        "city_id": chennai_city,
                        "panchayat_id": None,
                        "latitude": base_lat + offset,
                        "longitude": base_lon + offset,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    ward_created += 1

        # --- Panchayat-based CPs (multiple per panchayat) ---
        panchayats = list(
            Panchayat.objects.filter(
                company_id=company, project_id=project, is_deleted=False
            ).order_by("panchayat_name")
        )
        pan_created = 0
        for panchayat in panchayats:
            pan_num = "".join(filter(str.isdigit, panchayat.panchayat_name)) or "0"
            base_lat = float(panchayat.latitude) if panchayat.latitude else 13.1500
            base_lon = float(panchayat.longitude) if panchayat.longitude else 80.2000
            for stop_no in range(1, self.POINTS_PER_AREA + 1):
                cp_name = f"CP-PAN{pan_num}-{stop_no:02d}"
                offset = 0.0005 * stop_no
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
                        "latitude": base_lat + offset,
                        "longitude": base_lon + offset,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    pan_created += 1

        total = ward_created + pan_created
        self.log(
            f"---Collection Points seeded | ward CPs created={ward_created}/{len(wards) * self.POINTS_PER_AREA} "
            f"| panchayat CPs created={pan_created}/{len(panchayats) * self.POINTS_PER_AREA} | new total={total}---"
        )
