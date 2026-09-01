"""Daily operations seeders — trip assignments and the day's collection runs.

Ordered by dependency: everything here needs the trip plans seeded in
schedule_setup. The driver_* and retrip/breakdown seeders build demo
scenarios on top of those assignments and are run individually.
"""

from .daily_trip_assignment import DailyTripAssignmentSeeder
from .daily_trip_collection_point import DailyTripCollectionPointSeeder
from .driver_household_trip import DriverHouseholdTripSeeder
from .driver_wet_dry_bin_trips import DriverWetDryBinTripsSeeder
from .vehicle_breakdown import VehicleBreakdownSeeder
from .retrip_demo import RetripDemoSeeder

DAILY_OPERATIONS_SEEDERS = [
    DailyTripAssignmentSeeder,
    DailyTripCollectionPointSeeder,
]

__all__ = [
    "DailyTripAssignmentSeeder",
    "DailyTripCollectionPointSeeder",
    "DriverHouseholdTripSeeder",
    "DriverWetDryBinTripsSeeder",
    "VehicleBreakdownSeeder",
    "RetripDemoSeeder",
    "DAILY_OPERATIONS_SEEDERS",
]
