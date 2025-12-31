# seeders/masters/ward.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.continent import Continent
from api.apps.country import Country
from api.apps.state import State
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward, GeoFencingType, AreaType


class WardSeeder(BaseSeeder):
    name = "ward"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")
        zone_1 = Zone.objects.get(name="Zone 1")

        ward_defaults = {
            "continent_id": asia,
            "country_id": india,
            "state_id": tamil_nadu,
            "district_id": chennai_dist,
            "city_id": chennai_city,
            "zone_id": zone_1,
            "coordinates": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [80.2707, 13.0827],
                        [80.2757, 13.0827],
                        [80.2757, 13.0877],
                        [80.2707, 13.0877],
                        [80.2707, 13.0827]
                    ]
                ]
            },
            "geofencing_type": GeoFencingType.POLYGON,
            "geofencing_color": "#FF5733",
            "area_type": AreaType.URBAN,
            "is_active": True,
            "is_deleted": False,
        }

        ward, created = Ward.objects.update_or_create(
            name="Ward 1",
            city_id=chennai_city,
            zone_id=zone_1,
            defaults=ward_defaults
        )

        action = "Created" if created else "Updated"
        self.log(f"Ward seeded: {ward.name} ({action})")
