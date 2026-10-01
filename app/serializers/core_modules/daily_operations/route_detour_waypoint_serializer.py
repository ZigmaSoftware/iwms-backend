from rest_framework import serializers

from app.models.core_modules.daily_operations.route_detour_waypoint import RouteDetourWaypoint


class RouteDetourWaypointSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    class Meta:
        model = RouteDetourWaypoint
        fields = [
            "unique_id",
            "trip_plan_id",
            "trip_assignment_id",
            "after_stop_id",
            "sequence",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        # Routes are edited on the trip plan only; daily trips follow it.
        if attrs.get("trip_assignment_id"):
            raise serializers.ValidationError(
                {"trip_assignment_id": "Detours are drawn on the trip plan, not on a daily trip."}
            )
        # A partial update (moving a detour) keeps the detour's plan.
        if not (attrs.get("trip_plan_id") or getattr(self.instance, "trip_plan_id", None)):
            raise serializers.ValidationError({"trip_plan_id": "This field is required."})
        attrs["trip_assignment_id"] = None
        return attrs
