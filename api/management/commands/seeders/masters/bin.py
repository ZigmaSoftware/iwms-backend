# seeders/masters/bin.py
from django.utils import timezone

from api.management.commands.seeders.base import BaseSeeder
from api.apps.ward import Ward
from api.apps.bin import Bin, BinType, WasteType, BinStatus


class BinSeeder(BaseSeeder):
    name = "bin"

    def run(self):
        ward_1 = Ward.objects.get(name="Ward 1")

        Bin.objects.get_or_create(
            bin_name="Bin 1",
            ward=ward_1,
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

        self.log("Bins seeded")
