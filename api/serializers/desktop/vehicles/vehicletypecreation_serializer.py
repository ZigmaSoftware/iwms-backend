from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.models.vehicles.vehicleTypeCreation import VehicleTypeCreation
from api.validators.unique_name_validator import unique_name_validator


class VehicleTypeCreationSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = VehicleTypeCreation
        fields = "__all__"

        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(
            Model=VehicleTypeCreation,
            name_field="vehicleType",
        )(self, attrs)
