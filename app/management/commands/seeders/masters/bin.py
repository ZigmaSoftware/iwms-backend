# seeders/masters/bin.py
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.ward import Ward
from app.models.assets.bin import Bin, BinType, WasteType, BinStatus
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class BinSeeder(BaseSeeder):
    name = "bin"

    def run(self):
        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={
                "description": "Integrated Waste Management System",
                "is_active": True,
                "is_deleted": False,
            },
        )
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
        ward_1 = Ward.objects.get(name="Ward 1")

        Bin.objects.get_or_create(
            bin_name="Bin 1",
            ward=ward_1,
            company_id=company,
            project_id=project,
            defaults={
                "bin_type": BinType.PUBLIC,
                "waste_type": WasteType.MIXED,
                "color_code": "Green",
                "capacity_liters": 240,
                "latitude": 13.082680,
                "longitude": 80.270718,
                "installation_date": timezone.now().date(),
                "expected_life_years": 5,
                "bin_status": BinStatus.ACTIVE,
                "is_active": True,
                "is_deleted": False,
            },
        )

        self.log("---Bins seeded---")
