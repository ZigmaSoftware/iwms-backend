# seeders/masters/city.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.continent import Continent
from api.apps.country import Country
from api.apps.state import State
from api.apps.district import District
from api.apps.city import City
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

        self.log("Cities seeded")
