# core/management/commands/seeders/vehicles/__init__.py
from .vehicleCreation import VehicleCreationSeeder

VEHICLE_SEEDERS = [
    VehicleCreationSeeder,
]
