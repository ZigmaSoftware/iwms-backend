# seeders/masters/country.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.commonmasters.continent import Continent
from app.models.commonmasters.country import Country
class CountrySeeder(BaseSeeder):
    name = "country"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        Country.objects.get_or_create(name="India", continent_id=asia)
        self.log("---Countries seeded---")
