# seeders/masters/state.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
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

        self.log("---States seeded---")
