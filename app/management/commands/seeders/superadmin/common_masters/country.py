# seeders/masters/country.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country


class CountrySeeder(BaseSeeder):
    name = "country"

    # (country_name, continent_name)
    COUNTRIES = [
        ("India",       "Asia"),
        ("China",       "Asia"),
        ("Japan",       "Asia"),
        ("Bangladesh",  "Asia"),
        ("Pakistan",    "Asia"),
        ("Sri Lanka",   "Asia"),
        ("Nepal",       "Asia"),
        ("Myanmar",     "Asia"),
        ("Thailand",    "Asia"),
        ("Vietnam",     "Asia"),
        ("Malaysia",    "Asia"),
        ("Indonesia",   "Asia"),
        ("Philippines", "Asia"),
        ("Singapore",   "Asia"),
        ("South Korea", "Asia"),
    ]

    def run(self):
        continent_cache = {}
        for country_name, continent_name in self.COUNTRIES:
            if continent_name not in continent_cache:
                continent_cache[continent_name] = Continent.objects.get(name=continent_name)
            Country.objects.get_or_create(
                name=country_name,
                continent_id=continent_cache[continent_name],
            )

        self.log(f"---Countries seeded ({len(self.COUNTRIES)} records)---")
