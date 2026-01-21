from rest_framework import serializers

from api.apps.routeplan import RoutePlan


class RoutePlanSerializer(serializers.ModelSerializer):
    SUPERVISOR_ROLE_NAME = "supervisor"

    district_name = serializers.CharField(
        source="district_id.name", read_only=True
    )
    city_name = serializers.CharField(
        source="city_id.name", read_only=True
    )
    vehicle_no = serializers.CharField(
        source="vehicle_id.vehicle_no", read_only=True
    )

    supervisor_name = serializers.CharField(
        source="supervisor_id.staff_id.employee_name",
        read_only=True
    )

    class Meta:
        model = RoutePlan
        fields = [
            "id",
            "unique_id",

            # Foreign keys (IDs)
            "district_id",
            "city_id",
            "vehicle_id",
            "supervisor_id",

            # Human-readable names
            "district_name",
            "city_name",
            "vehicle_no",
            "supervisor_name",

            "status",
            "created_at",
        ]
        read_only_fields = ("id", "unique_id", "created_at")

    def validate_supervisor_id(self, value):
        """Ensure only supervisor user type is assigned to the route plan."""
        staff_role = getattr(value.staffusertype_id, "name", None)
        if not staff_role or staff_role.lower() != self.SUPERVISOR_ROLE_NAME:
            raise serializers.ValidationError(
                "Only users with the supervisor staff user type can lead a route plan."
            )
        return value
