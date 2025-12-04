from rest_framework import serializers
from api.apps.subproperty import SubProperty
from api.validators.unique_name_validator import unique_name_validator


class SubPropertySerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(
        source="property_id.property_name", 
        read_only=True
    )

    class Meta:
        model = SubProperty
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []   # disable built-in unique-together

    def validate_property_id(self, prop):
        if prop.is_deleted:
            raise serializers.ValidationError("Selected Property is deleted.")
        if not prop.is_active:
            raise serializers.ValidationError("Selected Property is inactive.")
        return prop

    def validate(self, attrs):
        # CALL THE UTILITY HERE
        return unique_name_validator(
            Model=SubProperty,
            name_field="sub_property_name",
            scope_fields=["property_id"]
        )(self, attrs)
