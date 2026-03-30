from .fuel import FuelSeeder
from .trip import TripSeeder
from .trip_attendance import TripAttendanceSeeder
from .trip_definition import TripDefinitionSeeder
from .trip_instance import TripInstanceSeeder
from .vehicleCreation import VehicleCreationSeeder
from .vehicleTypeCreation import VehicleTypeCreationSeeder

TRANSPORT_MASTER_SEEDERS = [
    FuelSeeder,
    VehicleTypeCreationSeeder,
    VehicleCreationSeeder,
    TripSeeder,
    TripDefinitionSeeder,
    TripInstanceSeeder,
    TripAttendanceSeeder,
]
