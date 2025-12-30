from rest_framework import serializers

from api.apps.route_run import RouteRun, RouteRunStop
from api.apps.route_stop import RouteStop


class RouteRunStopSerializer(serializers.ModelSerializer):
    route_stop_unique_id = serializers.CharField(
        source="route_stop.unique_id", read_only=True
    )

    class Meta:
        model = RouteRunStop
        fields = [
            "id",
            "route_stop",
            "route_stop_unique_id",
            "sequence_no",
            "status",
            "actual_arrival_at",
            "actual_departure_at",
        ]
        read_only_fields = ["id", "route_stop_unique_id"]


class RouteRunSerializer(serializers.ModelSerializer):
    stops = RouteRunStopSerializer(many=True, read_only=True)

    class Meta:
        model = RouteRun
        fields = [
            "unique_id",
            "route_id",
            "staff_template",
            "vehicle_type",
            "vehicle",
            "optimized_at",
            "is_active",
            "is_deleted",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "stops",
        ]
        read_only_fields = [
            "unique_id",
            "optimized_at",
            "is_deleted",
            "created_at",
            "updated_at",
            "stops",
        ]

    def validate(self, attrs):
        route_id = attrs.get("route_id") or getattr(self.instance, "route_id", None)
        staff_template = attrs.get("staff_template") or getattr(
            self.instance, "staff_template", None
        )
        if not route_id:
            raise serializers.ValidationError({"route_id": "Route ID is required."})
        if not staff_template:
            raise serializers.ValidationError(
                {"staff_template": "Staff template is required."}
            )
        if not RouteStop.objects.filter(
            route_id=route_id, is_active=True, is_deleted=False
        ).exists():
            raise serializers.ValidationError(
                {"route_id": "No active route stops found for this route."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        validated_data.setdefault("created_by", user if getattr(user, "is_authenticated", False) else None)
        route_run = super().create(validated_data)
        route_run.copy_stops_from_template()
        return route_run
