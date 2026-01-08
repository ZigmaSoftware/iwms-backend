# core/management/commands/seeders/vehicles/__init__.py
from .vehicleCreation import VehicleCreationSeeder
from ..userCreation.routeplan_seeder import RoutePlanSeeder

VEHICLE_SEEDERS = [
    VehicleCreationSeeder,
    RoutePlanSeeder,
]
