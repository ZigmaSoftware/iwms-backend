from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_trip_plan_static_route_id():
    return f"TPSR-{generate_unique_id()}"


class TripPlanStaticRoute(BaseMaster):
    """A trip plan's saved static route — the stop order, detours and road
    path, re-saved automatically whenever the plan's detours or stops change
    (or by "Save Route" on the Static Route Map).

    Each DailyTripAssignment generated from the plan gets its own copy
    (DailyTripStaticRoute), refreshed while the trip hasn't finished.
    `stops` / `detour_waypoints` use the RouteStop / waypoint shapes from
    app.services.static_route.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_trip_plan_static_route_id,
        editable=False,
    )

    trip_plan_id = models.CharField(max_length=30, unique=True)

    stops = models.JSONField(default=list)
    detour_waypoints = models.JSONField(default=list)
    # GeoJSON from OpenRouteService; null when routing was unavailable at
    # save time (the map then routes it live).
    route_geojson = models.JSONField(null=True, blank=True)
    distance_meters = models.FloatField(default=0)
    duration_seconds = models.FloatField(default=0)

    # Bumped on every save; daily copies record which version they took.
    version = models.PositiveIntegerField(default=1)
    saved_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_plan_id"]

    def __str__(self):
        return f"{self.trip_plan_id} v{self.version}"

    @property
    def trip_plan(self):
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        if self.trip_plan_id:
            return TripPlan.objects.filter(unique_id=self.trip_plan_id).first()
        return None
