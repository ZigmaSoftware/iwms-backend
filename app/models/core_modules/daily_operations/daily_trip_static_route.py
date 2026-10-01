from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_daily_trip_static_route_id():
    return f"DTSR-{generate_unique_id()}"


class DailyTripStaticRoute(BaseMaster):
    """One daily trip's copy of its trip plan's saved static route
    (TripPlanStaticRoute), taken when the trip is created and refreshed
    every time the plan's route changes while the trip is Scheduled or In
    Progress. Once the trip is completed (or its day has passed) it keeps
    the route it ran with.

    Only the route is frozen here; each stop's collection status is still
    read live from the trip's daily rows.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_daily_trip_static_route_id,
        editable=False,
    )

    trip_assignment_id = models.CharField(max_length=30, unique=True)
    trip_plan_id = models.CharField(max_length=30, null=True, blank=True)
    plan_route_version = models.PositiveIntegerField(default=1)

    stops = models.JSONField(default=list)
    detour_waypoints = models.JSONField(default=list)
    route_geojson = models.JSONField(null=True, blank=True)
    distance_meters = models.FloatField(default=0)
    duration_seconds = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_assignment_id"]

    def __str__(self):
        return f"{self.trip_assignment_id} ({self.trip_plan_id} v{self.plan_route_version})"

    @property
    def trip_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        if self.trip_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        return None
