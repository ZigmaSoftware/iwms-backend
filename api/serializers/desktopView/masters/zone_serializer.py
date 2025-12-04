from rest_framework import serializers
from api.apps.zone import Zone
from api.validators.unique_name_validator import unique_name_validator

class ZoneSerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_name   = serializers.CharField(source="country_id.name", read_only=True)
    state_name     = serializers.CharField(source="state_id.name", read_only=True)
    district_name  = serializers.CharField(source="district_id.name", read_only=True)
    city_name      = serializers.CharField(source="city_id.name", read_only=True)

    class Meta:
        model = Zone
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=Zone,
            scope_fields=[
                "continent_id",
                "country_id",
                "state_id",
                "district_id",
                "city_id"
            ]
        )(self, attrs)
