# seeders/masters/country.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.continent import Continent
from api.apps.country import Country
class CountrySeeder(BaseSeeder):
    name = "country"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        Country.objects.get_or_create(name="India", continent_id=asia)
        self.log("Countries seeded")
