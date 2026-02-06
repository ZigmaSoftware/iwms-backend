# seeders/masters/zone.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone, GeoFencingType, AreaType


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
        self.log(f"---Zone seeded: {zone.name} ({action})---")
