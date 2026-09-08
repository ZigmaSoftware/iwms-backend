from rest_framework import serializers
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.transport_masters.fuel import Fuel
from app.models.staff_creations.staffcreation import Staffcreation
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator


class VehicleCreationSerializer(serializers.ModelSerializer):

    # Read fields — return IDs and names in response
    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    project_id = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    # Write fields — accept IDs from frontend
    company_id_input = serializers.CharField(
        write_only=True,
        required=True,
    )
    project_id_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    vehicle_type_id = NameOrUniqueIdField(
        source="vehicle_type",
        name_field="vehicleType",
        queryset=VehicleTypeCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    fuel_type_id = NameOrUniqueIdField(
        source="fuel_type",
        name_field="fuel_type",
        queryset=Fuel.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    supervisor_id = NameOrUniqueIdField(
        source="supervisor",
        slug_field="staff_unique_id",
        name_field="employee_name",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    vehicle_type_name = serializers.CharField(
        source="vehicle_type.vehicleType",
        read_only=True
    )
    fuel_type_name = serializers.CharField(
        source="fuel_type.fuel_type",
        read_only=True
    )
    supervisor_name = serializers.CharField(
        source="supervisor.employee_name",
        read_only=True
    )

    is_assigned_today = serializers.SerializerMethodField()

    def get_is_assigned_today(self, obj):
        return bool(getattr(obj, "is_assigned_today", False))

    class Meta:
        model = VehicleCreation
        fields = [
            "unique_id",
            "company_id",
            "company_id_input",
            "company_name",
            "project_id",
            "project_id_input",
            "project_name",
            "vehicle_type_id",
            "fuel_type_id",
            "supervisor_id",
            "supervisor_name",
            "vehicle_no",
            "capacity",
            "mileage_per_liter",
            "service_record",
            "vehicle_insurance",
            "insurance_expiry_date",
            "vehicle_condition",
            "fuel_tank_capacity",
            "rc_upload",
            "vehicle_insurance_file",
            "vehicle_type_name",
            "fuel_type_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "is_assigned_today",
        ]
        read_only_fields = ["unique_id"]
        validators = []

    def get_company_id(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "unique_id", None)

    def get_company_name(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "name", None)

    def get_project_id(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "unique_id", None)

    def get_project_name(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "name", None)

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        return unique_name_validator(
            Model=VehicleCreation,
            name_field="vehicle_no",
        )(self, attrs)