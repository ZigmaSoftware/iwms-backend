from .trip_exception_log import TripExceptionLogSeeder
from .vehicle_trip_audit import VehicleTripAuditSeeder

AUDIT_SEEDERS = [
    VehicleTripAuditSeeder,
    TripExceptionLogSeeder,
]
