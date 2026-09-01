from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward, GeoFencingType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


# 15 Chennai wards plus the Noida Ward B used by the Noida customer import.
# (ward_name, zone_name, city_name, district_name, state_name, latitude, longitude)
WARD_DATA = [
    ("Ward 1",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0840, 80.2720),
    ("Ward 2",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0855, 80.2735),
    ("Ward 3",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0870, 80.2750),
    ("Ward 4",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0885, 80.2765),
    ("Ward 5",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0900, 80.2780),
    ("Ward 6",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0915, 80.2795),
    ("Ward 7",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0930, 80.2810),
    ("Ward 8",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0945, 80.2825),
    ("Ward 9",  "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0960, 80.2840),
    ("Ward 10", "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0975, 80.2855),
    ("Ward 11", "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.0990, 80.2870),
    ("Ward 12", "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.1005, 80.2885),
    ("Ward 13", "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.1020, 80.2900),
    ("Ward 14", "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.1035, 80.2915),
    ("Ward 15", "Zone 1",        "Chennai City", "Chennai",            "Tamil Nadu",    13.1050, 80.2930),
    ("B",       "ZNE3-GAMMA-01", "Noida",        "Gautam Buddh Nagar", "Uttar Pradesh", 28.4744, 77.5040),
]


class WardSeeder(BaseSeeder):
    name = "ward"

    def run(self):
        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={
                "description": "Integrated Waste Management System",
                "is_active": True,
                "is_deleted": False,
            },
        )
        project, _ = Project.objects.get_or_create(
            name=f"{company.name} Main Project",
            company_id=company,
            defaults={
                "description": f"Default project for {company.name}",
                "is_active": True,
                "is_deleted": False,
            },
        )

        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        state_cache = {}
        district_cache = {}
        city_cache = {}
        zone_cache = {}

        created_count = 0
        for ward_name, zone_name, city_name, district_name, state_name, lat, lon in WARD_DATA:
            if state_name not in state_cache:
                state_cache[state_name] = State.objects.get(name=state_name)
            district_key = (district_name, state_name)
            if district_key not in district_cache:
                district_cache[district_key] = District.objects.get(
                    name=district_name,
                    state_id=state_cache[state_name],
                    country_id=india,
                    continent_id=asia,
                )
            city_key = (city_name, district_name, state_name)
            if city_key not in city_cache:
                city_cache[city_key] = City.objects.get(
                    name=city_name,
                    district_id=district_cache[district_key],
                    state_id=state_cache[state_name],
                    company_id=company,
                    project_id=project,
                )
            zone_key = (zone_name, city_name, district_name, state_name)
            if zone_key not in zone_cache:
                zone_cache[zone_key] = Zone.objects.get(
                    zone_name=zone_name,
                    city_id=city_cache[city_key],
                    company_id=company,
                    project_id=project,
                )
            _, created = Ward.objects.update_or_create(
                ward_name=ward_name,
                zone_id=zone_cache[zone_key],
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": state_cache[state_name],
                    "district_id": district_cache[district_key],
                    "city_id": city_cache[city_key],
                    "zone_id": zone_cache[zone_key],
                    "latitude": lat,
                    "longitude": lon,
                    "geofencing_type": GeoFencingType.POLYGON,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                created_count += 1

        self.log(f"---Wards seeded ({len(WARD_DATA)} records, {created_count} created)---")
