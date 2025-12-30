from rest_framework import serializers

from api.apps.daily_route_assignment import DailyRouteAssignment


class DailyRouteAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyRouteAssignment
        fields = [
            "unique_id",
            "vehicle_type",
            "staff_template",
            "route_run",
            "route_id",
            "vehicle_type_name",
            "staff_template_label",
            "route_run_stop_count",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "route_id",
            "vehicle_type_name",
            "staff_template_label",
            "route_run_stop_count",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    route_id = serializers.CharField(
        source="route_run.route_id", read_only=True
    )
    vehicle_type_name = serializers.CharField(
        source="vehicle_type.vehicleType", read_only=True
    )
    route_run_stop_count = serializers.SerializerMethodField()
    staff_template_label = serializers.SerializerMethodField()

    def get_staff_template_label(self, obj):
        staff = obj.staff_template
        primary_driver = (
            getattr(getattr(staff.primary_driver_id, "staff_id", None), "employee_name", None)
            or getattr(staff.primary_driver_id, "unique_id", "")
        )
        primary_operator = (
            getattr(getattr(staff.primary_operator_id, "staff_id", None), "employee_name", None)
            or getattr(staff.primary_operator_id, "unique_id", "")
        )
        return f"{primary_driver} / {primary_operator}".strip()

    def get_route_run_stop_count(self, obj):
        route_run = obj.route_run
        if not route_run:
            return 0
        return route_run.stops.count()

    def validate(self, attrs):
        route_run = attrs.get("route_run") or getattr(
            self.instance, "route_run", None
        )
        if not route_run:
            raise serializers.ValidationError(
                {"route_run": "Route run is required."}
            )
        return attrs
