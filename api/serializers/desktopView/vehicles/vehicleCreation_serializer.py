from rest_framework import serializers

from api.apps.vehicleCreation import VehicleCreation
from api.apps.vehicleTypeCreation import VehicleTypeCreation
from api.apps.fuel import Fuel
from api.validators.unique_name_validator import unique_name_validator


class UniqueIdOrPkField(serializers.SlugRelatedField):
    """
    Accepts related object via unique_id (preferred) or numeric PK; serializes as unique_id.
    """

    def to_representation(self, value):
        return getattr(value, self.slug_field, None) or super().to_representation(value)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise


class VehicleCreationSerializer(serializers.ModelSerializer):
    vehicle_type_id = UniqueIdOrPkField(
        source="vehicle_type",
        slug_field="unique_id",
        queryset=VehicleTypeCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    fuel_type_id = UniqueIdOrPkField(
        source="fuel_type",
        slug_field="unique_id",
        queryset=Fuel.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    vehicle_type_name = serializers.CharField(source="vehicle_type.vehicleType", read_only=True)
    fuel_type_name = serializers.CharField(source="fuel_type.fuel_type", read_only=True)

    class Meta:
        model = VehicleCreation
        fields = [
            "id",
            "unique_id",
            "vehicle_type_id",
            "fuel_type_id",
            "vehicle_no",
            "capacity",
            "mileage_per_liter",
            "service_record",
            "vehicle_insurance",
            "insurance_expiry_date",
            "condition",
            "fuel_tank_capacity",
            "rc_upload",
            "vehicle_insurance_file",
            "vehicle_type_name",
            "fuel_type_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(
            Model=VehicleCreation,
            name_field="vehicle_no",
        )(self, attrs)
