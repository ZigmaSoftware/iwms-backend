from django.db import models


class StaticRouteAuditLog(models.Model):
    """One row per change to a trip plan's static route: the route before
    and after the save, what changed between them, and which daily trips
    were moved onto the new route. Written by
    app.services.static_route.save_plan_static_route; never edited.

    Both routes are full snapshots (stops, detours, road path, distance,
    duration), so the audit still shows them after the plan's route has
    moved on or the plan is deleted.
    """

    CHANGE_CREATED = "CREATED"
    CHANGE_DETOUR_ADDED = "DETOUR_ADDED"
    CHANGE_DETOUR_MOVED = "DETOUR_MOVED"
    CHANGE_DETOUR_REMOVED = "DETOUR_REMOVED"
    CHANGE_STOPS_CHANGED = "STOPS_CHANGED"
    CHANGE_ROUTE_CHANGED = "ROUTE_CHANGED"
    CHANGE_RESAVED = "RESAVED"

    CHANGE_TYPE_CHOICES = [
        (CHANGE_CREATED, "Route created"),
        (CHANGE_DETOUR_ADDED, "Detour added"),
        (CHANGE_DETOUR_MOVED, "Detour moved"),
        (CHANGE_DETOUR_REMOVED, "Detour removed"),
        (CHANGE_STOPS_CHANGED, "Stops changed"),
        (CHANGE_ROUTE_CHANGED, "Route changed"),
        (CHANGE_RESAVED, "Re-saved (no change)"),
    ]

    TRIGGER_DETOUR_EDIT = "DETOUR_EDIT"
    TRIGGER_TRIP_PLAN_EDIT = "TRIP_PLAN_EDIT"
    TRIGGER_MANUAL_SAVE = "MANUAL_SAVE"
    TRIGGER_SYSTEM = "SYSTEM"

    TRIGGER_CHOICES = [
        (TRIGGER_DETOUR_EDIT, "Static Route Map"),
        (TRIGGER_TRIP_PLAN_EDIT, "Trip Plan form"),
        (TRIGGER_MANUAL_SAVE, "Save Route"),
        (TRIGGER_SYSTEM, "System"),
    ]

    company_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    project_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    trip_plan_id = models.CharField(max_length=30, db_index=True)
    # Kept as text so the row still reads well if the plan is renamed/deleted.
    trip_plan_code = models.CharField(max_length=100, null=True, blank=True)

    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES, db_index=True)
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_SYSTEM)

    # Route versions on TripPlanStaticRoute; previous is null for the first save.
    previous_version = models.PositiveIntegerField(null=True, blank=True)
    new_version = models.PositiveIntegerField()

    # Full snapshots: {"stops", "detour_waypoints", "route_geojson",
    # "distance_meters", "duration_seconds"}. previous_route is null for the
    # first save.
    previous_route = models.JSONField(null=True, blank=True)
    new_route = models.JSONField()

    # What changed — see app.services.static_route.route_diff for the shape.
    changes = models.JSONField(default=dict)
    distance_change_meters = models.FloatField(default=0)
    duration_change_seconds = models.FloatField(default=0)

    # Daily trips moved onto the new route by this save.
    affected_trip_ids = models.JSONField(default=list)
    affected_trip_count = models.PositiveIntegerField(default=0)

    routing_error = models.CharField(max_length=255, null=True, blank=True)

    # Account.account_id of whoever made the change.
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "static_route_audit_logs"
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        return f"{self.trip_plan_code or self.trip_plan_id} v{self.previous_version}→v{self.new_version} {self.change_type}"
