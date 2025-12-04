from rest_framework import serializers
from api.apps.vehicleTypeCreation import VehicleTypeCreation
from api.validators.unique_name_validator import unique_name_validator


class VehicleTypeCreationSerializer(serializers.ModelSerializer):
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