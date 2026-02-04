# seeders/masters/city.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.commonmasters.continent import Continent
from app.models.commonmasters.country import Country
from app.models.commonmasters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
class CitySeeder(BaseSeeder):
    name = "city"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")

        City.objects.get_or_create(
            name="Chennai City",
            continent_id=asia,
            country_id=india,
            state_id=tamil_nadu,
            district_id=chennai_dist,
        )

        self.log("---Cities seeded---")
