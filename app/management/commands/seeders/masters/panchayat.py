from app.management.commands.seeders.base import BaseSeeder

# Common Masters
from app.models.common_masters.state import State

# Masters
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.panchayat import Panchayat, GeoFencingType
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy

# Super Admin
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class PanchayatSeeder(BaseSeeder):
    name = "panchayat"

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
        # AREA TYPE (Rural Only)
        # --------------------------------------------------
        rural_area_type = AreaType.objects.get(name="Rural")

        # --------------------------------------------------
        # HIERARCHY (Panchayat Level)
        # --------------------------------------------------
        hierarchy = AdministrativeHierarchy.objects.get(
            area_type=rural_area_type,
            level_name="Panchayat",
        )

        # --------------------------------------------------
        # CREATE / UPDATE PANCHAYAT
        # --------------------------------------------------
        panchayat, created = Panchayat.objects.update_or_create(
            panchayat_name="Panchayat 1",
            company_id=company,
            project_id=project,
            defaults={
                "state_id": tamil_nadu,
                "district_id": chennai_dist,
                "city_id": chennai_city,
                "area_type_id": rural_area_type,
                "hierarchy_id": hierarchy,
                "geofencing_type": GeoFencingType.POLYGON,
                "agreed_weight_kg": 0,
                "weight_unit": "kg",
                "effective_from": None,
                "latitude": 13.150000,
                "longitude": 80.200000,
                "is_active": True,
                "is_deleted": False,
            },
        )

        action = "Created" if created else "Updated"
        self.log(f"---Panchayat seeded: {panchayat.panchayat_name} ({action})---")
