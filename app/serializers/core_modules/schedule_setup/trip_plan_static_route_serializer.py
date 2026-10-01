from rest_framework import serializers

from app.models.core_modules.schedule_setup.trip_plan_static_route import TripPlanStaticRoute


class TripPlanStaticRouteSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    class Meta:
        model = TripPlanStaticRoute
        fields = [
            "unique_id",
            "trip_plan_id",
            "stops",
            "detour_waypoints",
            "route_geojson",
            "distance_meters",
            "duration_seconds",
            "version",
            "saved_at",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        # Saved only through the viewset's create (Save Route), which builds
        # every field from the plan itself.
        read_only_fields = fields
