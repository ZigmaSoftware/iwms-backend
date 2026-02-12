from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.validators.unique_name_validator import unique_name_validator


class VehicleTypeCreationSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = VehicleTypeCreation
        exclude = ["id"]

        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(
            Model=VehicleTypeCreation,
            name_field="vehicleType",
        )(self, attrs)
