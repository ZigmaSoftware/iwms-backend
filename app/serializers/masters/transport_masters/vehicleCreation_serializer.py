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
        name_field="vehicleType",
        queryset=VehicleTypeCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    fuel_type_id = NameOrUniqueIdField(
        name_field="fuel_type",
        queryset=Fuel.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    supervisor_id = NameOrUniqueIdField(
        slug_field="staff_unique_id",
        name_field="employee_name",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    vehicle_type_name = serializers.SerializerMethodField()
    fuel_type_name = serializers.SerializerMethodField()
    supervisor_name = serializers.SerializerMethodField()

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
        return obj.company_id

    def get_company_name(self, obj):
        from app.models.superadmin_masters.company import Company
        company = Company.objects.filter(unique_id=obj.company_id).first()
        return company.name if company else None

    def get_project_id(self, obj):
        return obj.project_id

    def get_project_name(self, obj):
        from app.models.superadmin_masters.project import Project
        project = Project.objects.filter(unique_id=obj.project_id).first()
        return project.name if project else None

    def get_vehicle_type_name(self, obj):
        vehicle_type = VehicleTypeCreation.objects.filter(unique_id=obj.vehicle_type_id).first()
        return vehicle_type.vehicleType if vehicle_type else None

    def get_fuel_type_name(self, obj):
        fuel = Fuel.objects.filter(unique_id=obj.fuel_type_id).first()
        return fuel.fuel_type if fuel else None

    def get_supervisor_name(self, obj):
        supervisor = Staffcreation.objects.filter(staff_unique_id=obj.supervisor_id).first()
        return supervisor.employee_name if supervisor else None

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        return unique_name_validator(
            Model=VehicleCreation,
            name_field="vehicle_no",
        )(self, attrs)
