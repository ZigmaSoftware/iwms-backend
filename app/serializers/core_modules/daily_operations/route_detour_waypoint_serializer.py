from rest_framework import serializers

from app.models.schedule_masters.route_detour_waypoint import RouteDetourWaypoint


class RouteDetourWaypointSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteDetourWaypoint
        fields = [
            "unique_id",
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
