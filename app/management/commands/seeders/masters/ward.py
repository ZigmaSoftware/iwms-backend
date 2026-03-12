# # seeders/masters/ward.py
# from app.management.commands.seeders.base import BaseSeeder
# from app.models.common_masters.continent import Continent
# from app.models.common_masters.country import Country
# from app.models.common_masters.state import State
# from app.models.masters.district import District
# from app.models.masters.city import City
# from app.models.masters.zone import Zone
# from app.models.masters.ward import Ward, GeoFencingType, AreaType
# from app.models.superadmin_masters.company import Company
# from app.models.superadmin_masters.project import Project


# class WardSeeder(BaseSeeder):
#     name = "ward"

#     def run(self):
#         company, _ = Company.objects.get_or_create(
#             name="IWMS",
#             defaults={
#                 "description": "Integrated Waste Management System",
#                 "is_active": True,
#                 "is_deleted": False,
#             },
#         )

#         project_name = f"{company.name} Main Project"
#         project, _ = Project.objects.get_or_create(
#             name=project_name,
#             company_id=company,
#             defaults={
#                 "description": f"Default project for {company.name}",
#                 "is_active": True,
#                 "is_deleted": False,
#             },
#         )

#         asia = Continent.objects.get(name="Asia")
#         india = Country.objects.get(name="India")
#         tamil_nadu = State.objects.get(name="Tamil Nadu")
#         chennai_dist = District.objects.get(name="Chennai")
#         chennai_city = City.objects.get(name="Chennai City")
#         zone_1 = Zone.objects.get(name="Zone 1")

#         ward_defaults = {
#             "continent_id": asia,
#             "country_id": india,
#             "state_id": tamil_nadu,
#             "district_id": chennai_dist,
#             "city_id": chennai_city,
#             "zone_id": zone_1,
#             "company_id": company,
#             "project_id": project,
#             "coordinates": {
#                 "type": "Polygon",
#                 "coordinates": [
#                     [
#                         [80.2707, 13.0827],
#                         [80.2757, 13.0827],
#                         [80.2757, 13.0877],
#                         [80.2707, 13.0877],
#                         [80.2707, 13.0827]
#                     ]
#                 ]
#             },
#             "geofencing_type": GeoFencingType.POLYGON,
#             "geofencing_color": "#FF5733",
#             "area_type": AreaType.URBAN,
#             "is_active": True,
#             "is_deleted": False,
#         }

#         ward, created = Ward.objects.update_or_create(
#             name="Ward 1",
#             city_id=chennai_city,
#             zone_id=zone_1,
#             company_id=company,
#             project_id=project,
#             defaults=ward_defaults
#         )

#         action = "Created" if created else "Updated"
#         self.log(f"---Ward seeded: {ward.name} ({action})---")


from app.management.commands.seeders.base import BaseSeeder

# Common Masters
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State

# Masters
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward, GeoFencingType
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy

# Super Admin
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class WardSeeder(BaseSeeder):
    name = "ward"

    def run(self):

        # --------------------------------------------------
        # COMPANY
        # --------------------------------------------------
        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={
                "description": "Integrated Waste Management System",
                "is_active": True,
                "is_deleted": False,
            },
        )

        # --------------------------------------------------
        # PROJECT
        # --------------------------------------------------
        project_name = f"{company.name} Main Project"
        project, _ = Project.objects.get_or_create(
            name=project_name,
            company_id=company,
            defaults={
                "description": f"Default project for {company.name}",
                "is_active": True,
                "is_deleted": False,
            },
        )

        # --------------------------------------------------
        # FETCH MASTER DATA
        # --------------------------------------------------
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        zone_1 = Zone.objects.get(
            zone_name="Zone 1",   # ✅ correct field
            city_id=chennai_city,
            company_id=company,
            project_id=project,
        )

        # --------------------------------------------------
        # AREA TYPE (Urban)
        # --------------------------------------------------
        urban_area_type = AreaType.objects.get(
            name="Urban",
            state_id=tamil_nadu,
            district_id=chennai_dist,
            city_id=chennai_city,
        )

        # --------------------------------------------------
        # ADMINISTRATIVE HIERARCHY (Ward Level)
        # --------------------------------------------------
        hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(
            area_type=urban_area_type,
            level_name="Ward",
        )

        # --------------------------------------------------
        # WARD DEFAULT VALUES
        # --------------------------------------------------
        ward_defaults = {
            "company_id": company,
            "project_id": project,
            "state_id": tamil_nadu,
            "district_id": chennai_dist,
            "city_id": chennai_city,
            "zone_id": zone_1,
            "area_type_id": urban_area_type,
            "hierarchy_id": hierarchy,
            "latitude": 13.0840,
            "longitude": 80.2720,
            "geofencing_type": GeoFencingType.POLYGON,
            "is_active": True,
            "is_deleted": False,
        }

        # --------------------------------------------------
        # CREATE OR UPDATE WARD
        # --------------------------------------------------
        ward, created = Ward.objects.update_or_create(
            ward_name="Ward 1",   # ✅ use correct field
            zone_id=zone_1,
            company_id=company,
            project_id=project,
            defaults=ward_defaults,
        )

        action = "Created" if created else "Updated"
        self.log(f"---Ward seeded: {ward.ward_name} ({action})---")