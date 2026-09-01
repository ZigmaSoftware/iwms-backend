"""Transport masters seeders — vehicle types, vehicles, fuel, trip attendance.

Ordered by dependency: vehicles need their type; trip attendance needs the
daily trip assignments seeded in core_modules/daily_operations.
"""

from .vehicleTypeCreation import VehicleTypeCreationSeeder
from .vehicleCreation import VehicleCreationSeeder
from .fuel import FuelSeeder

TRANSPORT_MASTER_SEEDERS = [
    VehicleTypeCreationSeeder,
    VehicleCreationSeeder,
    FuelSeeder,
]

__all__ = [
    "VehicleTypeCreationSeeder",
    "VehicleCreationSeeder",
    "FuelSeeder",
    "TRANSPORT_MASTER_SEEDERS",
]
