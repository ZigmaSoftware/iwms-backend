# seeders/masters/zone.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.continent import Continent
from api.apps.country import Country
from api.apps.state import State
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone


class ZoneSeeder(BaseSeeder):
    name = "zone"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        Zone.objects.get_or_create(
            name="Zone 1",
            continent_id=asia,
            country_id=india,
            state_id=tamil_nadu,
            district_id=chennai_dist,
            city_id=chennai_city,
        )

        self.log("Zones seeded")
