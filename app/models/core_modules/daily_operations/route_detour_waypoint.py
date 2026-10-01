from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_route_detour_waypoint_id():
    return f"RDW-{generate_unique_id()}"


class RouteDetourWaypoint(BaseMaster):
    """A manually placed point the road route must pass through on the
    Static Route Map — used to detour a leg around a closed/blocked road
    without reordering or moving the real stops.

    Belongs to a TripPlan: part of the plan's static route, shown on every
    daily trip generated from that plan. Routes are edited on the trip plan
    only. `trip_assignment_id` is legacy (old per-trip detours) — no longer
    written or shown. Deleted with its owner.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_route_detour_waypoint_id,
        editable=False,
    )

    trip_plan_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    trip_assignment_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)

    # The RouteStop.id this waypoint comes immediately after — i.e. which
    # leg it belongs to. A location key from app.services.static_route
    # ("cp:<collection_point_id>", "cust:<customer_id>", "plant:start"),
    # not a row id, so a plan's detour matches the same leg on every
    # daily trip generated from it.
    after_stop_id = models.CharField(max_length=64)

    sequence = models.PositiveIntegerField(default=1)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_plan_id", "trip_assignment_id", "after_stop_id", "sequence"]

    def __str__(self):
        return f"{self.trip_plan_id or self.trip_assignment_id}:{self.after_stop_id}:{self.sequence}"

    @property
    def trip_plan(self):
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        if self.trip_plan_id:
            return TripPlan.objects.filter(unique_id=self.trip_plan_id).first()
        return None

    @property
    def trip_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        if self.trip_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        return None
