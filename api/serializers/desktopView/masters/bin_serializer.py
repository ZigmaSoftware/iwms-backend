from rest_framework import serializers
from api.apps.bin import Bin
from api.validators.unique_name_validator import unique_name_validator


class BinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bin
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=Bin,
            name_field="name",
        )(self, attrs)
