# seeders/masters/continent.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.continent import Continent

class ContinentSeeder(BaseSeeder):
    name = "continent"

    def run(self):
        Continent.objects.get_or_create(name="Asia")
        Continent.objects.get_or_create(name="Europe")
        self.log("Continents seeded")
