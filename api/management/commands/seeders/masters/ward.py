# seeders/masters/ward.py
from api.management.commands.seeders.base import BaseSeeder
from api.models.commonmasters.continent import Continent
from api.models.commonmasters.country import Country
from api.models.commonmasters.state import State
from api.models.masters.district import District
from api.models.masters.city import City
from api.models.masters.zone import Zone
from api.models.masters.ward import Ward, GeoFencingType, AreaType


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
