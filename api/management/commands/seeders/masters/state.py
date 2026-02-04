# seeders/masters/state.py
from api.management.commands.seeders.base import BaseSeeder
from api.models.commonmasters.continent import Continent
from api.models.commonmasters.country import Country
from api.models.commonmasters.state import State
class StateSeeder(BaseSeeder):
    name = "state"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")

        State.objects.get_or_create(
            name="Tamil Nadu",
            country_id=india,
            continent_id=asia,
            defaults={"label": "TN"}
        )

        self.log("States seeded")
