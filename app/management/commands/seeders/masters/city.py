# seeders/masters/city.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class CitySeeder(BaseSeeder):
    name = "city"

    # (city_name, district_name, state_name)
    CITIES = [
        ("Chennai City",         "Chennai",              "Tamil Nadu"),
        ("Coimbatore City",      "Coimbatore",           "Tamil Nadu"),
        ("Madurai City",         "Madurai",              "Tamil Nadu"),
        ("Tiruchirappalli City", "Tiruchirappalli",      "Tamil Nadu"),
        ("Salem City",           "Salem",                "Tamil Nadu"),
        ("Tirunelveli City",     "Tirunelveli",          "Tamil Nadu"),
        ("Erode City",           "Erode",                "Tamil Nadu"),
        ("Vellore City",         "Vellore",              "Tamil Nadu"),
        ("Thoothukudi City",     "Thoothukudi",          "Tamil Nadu"),
        ("Dindigul City",        "Dindigul",             "Tamil Nadu"),
        ("Thanjavur City",       "Thanjavur",            "Tamil Nadu"),
        ("Ranipet City",         "Ranipet",              "Tamil Nadu"),
        ("Kancheepuram City",    "Kancheepuram",         "Tamil Nadu"),
        ("Chengalpattu City",    "Chengalpattu",         "Tamil Nadu"),
        ("Tiruvannamalai City",  "Tiruvannamalai",       "Tamil Nadu"),
        ("Noida",                "Gautam Buddh Nagar",   "Uttar Pradesh"),
    ]

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

        for city_name, district_name, state_name in self.CITIES:
            if state_name not in state_cache:
                state_cache[state_name] = State.objects.get(name=state_name)
            district_key = (district_name, state_name)
            if district_key not in district_cache:
                district_cache[district_key] = District.objects.get(
                    name=district_name, state_id=state_cache[state_name]
                )
            City.objects.get_or_create(
                name=city_name,
                continent_id=asia,
                country_id=india,
                state_id=state_cache[state_name],
                district_id=district_cache[district_key],
                company_id=company,
                project_id=project,
            )

        self.log(f"---Cities seeded ({len(self.CITIES)} records)---")
