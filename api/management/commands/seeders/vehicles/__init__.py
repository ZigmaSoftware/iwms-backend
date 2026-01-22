# core/management/commands/seeders/vehicles/__init__.py
from .vehicleCreation import VehicleCreationSeeder
from .bin_load_log import BinLoadLogSeeder
from ..assets.zone_property_load_tracker import ZonePropertyLoadTrackerSeeder
from ..userCreation.routeplan_seeder import RoutePlanSeeder
VEHICLE_SEEDERS = [
    VehicleCreationSeeder,
    ZonePropertyLoadTrackerSeeder,
    RoutePlanSeeder,
    BinLoadLogSeeder,
]
