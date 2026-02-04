# seeders/masters/continent.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.commonmasters.continent import Continent

class ContinentSeeder(BaseSeeder):
    name = "continent"

    def run(self):
        Continent.objects.get_or_create(name="Asia")
        Continent.objects.get_or_create(name="Europe")
        self.log("Continents seeded")
