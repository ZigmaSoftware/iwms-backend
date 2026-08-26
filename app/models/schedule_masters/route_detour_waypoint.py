from django.db import models

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_route_detour_waypoint_id():
    return f"RDW-{generate_unique_id()}"


class RouteDetourWaypoint(BaseMaster):
    """A manually placed point the road route must pass through, for one
    specific DailyTripAssignment's Static Route Map — used to detour a leg
    around a closed/blocked road without reordering or moving the real
    stops. Scoped to one trip only; deleted with it.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_route_detour_waypoint_id,
        editable=False,
    )

    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.CASCADE,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="route_detour_waypoints",
    )

    # The RouteStop.id this waypoint comes immediately after — i.e. which
    # leg it belongs to. Plain string, not an FK: the stop before a leg can
    # be the synthetic "start" entry, which has no DB row of its own.
    after_stop_id = models.CharField(max_length=30)

    sequence = models.PositiveIntegerField(default=1)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_assignment_id", "after_stop_id", "sequence"]

    def __str__(self):
        return f"{self.trip_assignment_id_id}:{self.after_stop_id}:{self.sequence}"
