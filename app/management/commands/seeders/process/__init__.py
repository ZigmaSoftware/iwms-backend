from .routeplan_seeder import RoutePlanSeeder
from .zone_property_load_tracker import ZonePropertyLoadTrackerSeeder

PROCESS_SEEDERS = [
    ZonePropertyLoadTrackerSeeder,
    RoutePlanSeeder,
]
