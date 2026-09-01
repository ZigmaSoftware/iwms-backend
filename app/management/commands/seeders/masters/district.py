# seeders/masters/district.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class DistrictSeeder(BaseSeeder):
    name = "district"

    # (district_name, state_name)
    DISTRICTS = [
        ("Chennai", "Tamil Nadu"),
        ("Coimbatore", "Tamil Nadu"),
        ("Madurai", "Tamil Nadu"),
        ("Tiruchirappalli", "Tamil Nadu"),
        ("Salem", "Tamil Nadu"),
        ("Tirunelveli", "Tamil Nadu"),
        ("Erode", "Tamil Nadu"),
        ("Vellore", "Tamil Nadu"),
        ("Thoothukudi", "Tamil Nadu"),
        ("Dindigul", "Tamil Nadu"),
        ("Thanjavur", "Tamil Nadu"),
        ("Ranipet", "Tamil Nadu"),
        ("Kancheepuram", "Tamil Nadu"),
        ("Chengalpattu", "Tamil Nadu"),
        ("Tiruvannamalai", "Tamil Nadu"),
        ("Gautam Buddh Nagar", "Uttar Pradesh"),
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

        for name, state_name in self.DISTRICTS:
            if state_name not in state_cache:
                state_cache[state_name] = State.objects.get(name=state_name)
            District.objects.get_or_create(
                name=name,
                state_id=state_cache[state_name],
                country_id=india,
                continent_id=asia,
                company_id=company,
                project_id=project,
            )

        self.log(f"---Districts seeded ({len(self.DISTRICTS)} records)---")
