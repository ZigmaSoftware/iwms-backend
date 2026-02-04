# seeders/masters/zone.py
from api.management.commands.seeders.base import BaseSeeder
from api.models.commonmasters.continent import Continent
from api.models.commonmasters.country import Country
from api.models.commonmasters.state import State
from api.models.masters.district import District
from api.models.masters.city import City
from api.models.masters.zone import Zone, GeoFencingType, AreaType


class ZoneSeeder(BaseSeeder):
    name = "zone"

    def run(self):
        # -----------------------------
        # FETCH MASTER DATA
        # -----------------------------
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        # -----------------------------
        # ZONE DEFAULTS
        # -----------------------------
        zone_defaults = {
            "continent_id": asia,
            "country_id": india,
            "state_id": tamil_nadu,
            "district_id": chennai_dist,
            "city_id": chennai_city,
            "coordinates": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [80.2500, 13.0800],
                        [80.3000, 13.0800],
                        [80.3000, 13.1200],
                        [80.2500, 13.1200],
                        [80.2500, 13.0800]
                    ]
                ]
            },
            "geofencing_type": GeoFencingType.POLYGON,
            "geofencing_color": "#3498DB",
            "area_type": AreaType.URBAN,
            "is_active": True,
            "is_deleted": False,
        }

        # -----------------------------
        # CREATE / UPDATE ZONE
        # -----------------------------
        zone, created = Zone.objects.update_or_create(
            name="Zone 1",
            city_id=chennai_city,
            defaults=zone_defaults
        )

        action = "Created" if created else "Updated"
        self.log(f"Zone seeded: {zone.name} ({action})")
