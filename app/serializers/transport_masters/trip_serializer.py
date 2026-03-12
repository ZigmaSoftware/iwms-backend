from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.transport_masters.trip import Trip
from app.validators.unique_name_validator import unique_name_validator
from app.models.user_creations.stafftemplate import StaffTemplate




class TripSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    vehicle_no = serializers.CharField(source = "vehicle_id.vehicle_no", read_only = True)
    operator_id = serializers.CharField(source = "staff_id.operator_id", read_only  = True)
    operator_name = serializers.CharField(source = "staff_id.operator_name", read_only  = True)
    driver_id = serializers.CharField(source = "staff_id.driver_id", read_only  = True)
    driver_name = serializers.CharField(source = "staff_id.driver_name", read_only  = True)
    wastetype_name = serializers.CharField(source = "waste_type_id.waste_type_name", read_only  = True)

    staff_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.all()
    )


    class Meta:
        model = Trip
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "vehicle_id",
            "vehicle_no",
            "waste_type_id",
            "wastetype_name",
            "staff_id",
            "operator_id",
            "operator_name",
            "driver_id",
            "driver_name",
            "is_completed",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

