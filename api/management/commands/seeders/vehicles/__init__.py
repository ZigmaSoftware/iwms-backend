# core/management/commands/seeders/vehicles/__init__.py
from .vehicleCreation import VehicleCreationSeeder
from ..userCreation.routeplan_seeder import RoutePlanSeeder
from ..customers.household_pickup_event import HouseholdPickupEventSeeder

VEHICLE_SEEDERS = [
    VehicleCreationSeeder,
    RoutePlanSeeder,
    HouseholdPickupEventSeeder,
]
