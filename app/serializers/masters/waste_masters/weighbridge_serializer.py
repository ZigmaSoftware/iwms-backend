from rest_framework import serializers
from app.models.masters.waste_masters.weighbridge import WeighbridgeCheck
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField


class WeighbridgeCheckSerializer(TenancyReadSerializerMixin,serializers.ModelSerializer):

    trip_id = UniqueIdOrPkField(
        queryset=TripPlan.objects.filter(is_deleted=False)
    )

    vehicle_no = serializers.CharField(source = "trip_id.vehicle_id.vehicle_no", read_only = True)
    wastetype = serializers.CharField(source = "trip_id.waste_type_id.waste_type_name", read_only = True)
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)


    class Meta:
        model = WeighbridgeCheck
        fields = [
            "unique_id",
            "trip_id",
            "vehicle_no",
            "wastetype",
            "total_collected_weight",
            "weighbridge_weight",
            "weight_difference",
            "status",
            "checked_date",
            "collected_date",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id", "weight_difference", "status"]
