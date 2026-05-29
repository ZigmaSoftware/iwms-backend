from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.process.routeplan import RoutePlan


class RoutePlanSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    SUPERVISOR_ROLE_NAMES = {"supervisor", "company supervisor", "contractor supervisor"}

    district_name = serializers.CharField(
        source="district_id.name", read_only=True
    )
    city_name = serializers.CharField(
        source="city_id.name", read_only=True
    )
    zone_name = serializers.CharField(
        source="zone_id.zone_name", read_only=True, default=None
    )
    panchayat_name = serializers.CharField(
        source="panchayat_id.panchayat_name", read_only=True, default=None
    )
    vehicle_no = serializers.CharField(
        source="vehicle_id.vehicle_no", read_only=True
    )
    supervisor_name = serializers.CharField(
        source="supervisor_id.employee_name",
        read_only=True
    )
    driver_name = serializers.CharField(
        source="driver_id.employee_name", read_only=True, default=None
    )
    staff_template_code = serializers.CharField(
        source="staff_template_id.display_code", read_only=True, default=None
    )

    class Meta:
        model = RoutePlan
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "display_code",

            "district_id",
            "city_id",
            "zone_id",
            "panchayat_id",
            "staff_template_id",
            "driver_id",
            "vehicle_id",
            "supervisor_id",

            "district_name",
            "city_name",
            "zone_name",
            "panchayat_name",
            "vehicle_no",
            "supervisor_name",
            "driver_name",
            "staff_template_code",

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
        role_name = getattr(staff_type, "name", "").lower().strip()

        if role_name not in self.SUPERVISOR_ROLE_NAMES:
            raise serializers.ValidationError(
                "Only supervisors can be assigned to a route plan."
            )
        return value
