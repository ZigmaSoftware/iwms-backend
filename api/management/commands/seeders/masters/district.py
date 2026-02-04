# seeders/masters/district.py
from api.management.commands.seeders.base import BaseSeeder
from api.models.commonmasters.continent import Continent
from api.models.commonmasters.country import Country
from api.models.commonmasters.state import State
from api.models.masters.district import District


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
