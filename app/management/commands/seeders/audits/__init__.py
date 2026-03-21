from .bin_load_log import BinLoadLogSeeder
from .trip_exception_log import TripExceptionLogSeeder
from .vehicle_trip_audit import VehicleTripAuditSeeder

AUDIT_SEEDERS = [
    BinLoadLogSeeder,
    VehicleTripAuditSeeder,
    TripExceptionLogSeeder,
]
