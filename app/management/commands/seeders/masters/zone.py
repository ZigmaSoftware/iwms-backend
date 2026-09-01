from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone, GeoFencingType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


# 15 Chennai zones plus the Noida Gamma zone used by the Noida customer import.
# (zone_name, city_name, district_name, state_name, latitude, longitude)
ZONE_DATA = [
    ("Zone 1",          "Chennai City", "Chennai",            "Tamil Nadu",    13.0827, 80.2707),
    ("Zone 2",          "Chennai City", "Chennai",            "Tamil Nadu",    13.0900, 80.2800),
    ("Zone 3",          "Chennai City", "Chennai",            "Tamil Nadu",    13.0750, 80.2600),
    ("Zone 4",          "Chennai City", "Chennai",            "Tamil Nadu",    13.1000, 80.2900),
    ("Zone 5",          "Chennai City", "Chennai",            "Tamil Nadu",    13.0680, 80.2550),
    ("Zone 6",          "Chennai City", "Chennai",            "Tamil Nadu",    13.1100, 80.3000),
    ("Zone 7",          "Chennai City", "Chennai",            "Tamil Nadu",    13.0600, 80.2450),
    ("Zone 8",          "Chennai City", "Chennai",            "Tamil Nadu",    13.1200, 80.3100),
    ("Zone 9",          "Chennai City", "Chennai",            "Tamil Nadu",    13.0520, 80.2350),
    ("Zone 10",         "Chennai City", "Chennai",            "Tamil Nadu",    13.1300, 80.3200),
    ("Zone 11",         "Chennai City", "Chennai",            "Tamil Nadu",    13.0440, 80.2250),
    ("Zone 12",         "Chennai City", "Chennai",            "Tamil Nadu",    13.1400, 80.3300),
    ("Zone 13",         "Chennai City", "Chennai",            "Tamil Nadu",    13.0360, 80.2150),
    ("Zone 14",         "Chennai City", "Chennai",            "Tamil Nadu",    13.1500, 80.3400),
    ("Zone 15",         "Chennai City", "Chennai",            "Tamil Nadu",    13.0280, 80.2050),
    ("ZNE3-GAMMA-01",   "Noida",        "Gautam Buddh Nagar", "Uttar Pradesh", 28.4744, 77.5040),
]


class ZoneSeeder(BaseSeeder):
    name = "zone"

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

        created_count = 0
        for zone_name, city_name, district_name, state_name, lat, lon in ZONE_DATA:
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
                    country_id=india,
                    continent_id=asia,
                    company_id=company,
                    project_id=project,
                )
            _, created = Zone.objects.update_or_create(
                zone_name=zone_name,
                city_id=city_cache[city_key],
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": state_cache[state_name],
                    "district_id": district_cache[district_key],
                    "city_id": city_cache[city_key],
                    "latitude": lat,
                    "longitude": lon,
                    "geofencing_type": GeoFencingType.POLYGON,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                created_count += 1

        self.log(f"---Zones seeded ({len(ZONE_DATA)} records, {created_count} created)---")
