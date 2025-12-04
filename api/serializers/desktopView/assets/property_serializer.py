from rest_framework import serializers
from api.apps.property import Property
from api.validators.unique_name_validator import unique_name_validator

class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=Property,
            name_field="property_name",
        )(self, attrs)
