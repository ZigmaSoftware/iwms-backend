"""Schedule setup seeders — collection points, staff templates, trip plans.

Ordered by dependency: trip plans need collection points and staff
templates; the GNO variant is project-specific (Blue Planet / Greater
Noida) and is run on its own rather than as part of the default group.
"""

from .collection_point import CollectionPointSeeder
from .staff_template import StaffTemplateSeeder
from .alternative_staff_template import AlternativeStaffTemplateSeeder
from .trip_plan import TripPlanSeeder
from .trip_plan_collection_point import TripPlanCollectionPointSeeder
from .trip_plan_gno import TripPlanGNOSeeder

SCHEDULE_SETUP_SEEDERS = [
    CollectionPointSeeder,
    StaffTemplateSeeder,
    AlternativeStaffTemplateSeeder,
    TripPlanSeeder,
    TripPlanCollectionPointSeeder,
]

__all__ = [
    "CollectionPointSeeder",
    "StaffTemplateSeeder",
    "AlternativeStaffTemplateSeeder",
    "TripPlanSeeder",
    "TripPlanCollectionPointSeeder",
    "TripPlanGNOSeeder",
    "SCHEDULE_SETUP_SEEDERS",
]
