# seeders/masters/district.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.commonmasters.continent import Continent
from app.models.commonmasters.country import Country
from app.models.commonmasters.state import State
from app.models.masters.district import District


class DistrictSeeder(BaseSeeder):
    name = "district"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu")

        District.objects.get_or_create(
            name="Chennai",
            state_id=tamil_nadu,
            country_id=india,
            continent_id=asia,
        )

        self.log("Districts seeded")
