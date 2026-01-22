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
    zone_name = serializers.CharField(
        source="zone_id.name", read_only=True
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
            "unique_id",
            "display_code",

            "district_id",
            "city_id",
            "zone_id",
            "vehicle_id",
            "supervisor_id",

            "district_name",
            "city_name",
            "zone_name",
            "vehicle_no",
            "supervisor_name",

            "is_active",
            "created_at",
        ]

        read_only_fields = (
            "unique_id",
            "display_code",
            "created_at",
        )

    def validate_supervisor_id(self, value):
        staff_type = getattr(value, "staffusertype_id", None)
        role_name = getattr(staff_type, "name", "").lower()

        if role_name != self.SUPERVISOR_ROLE_NAME:
            raise serializers.ValidationError(
                "Only supervisors can be assigned to a route plan."
            )
        return value
