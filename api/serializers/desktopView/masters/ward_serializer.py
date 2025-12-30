from rest_framework import serializers
from api.apps.ward import Ward
from api.validators.unique_name_validator import unique_name_validator


class WardSerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_name   = serializers.CharField(source="country_id.name", read_only=True)
    state_name     = serializers.CharField(source="state_id.name", read_only=True)
    district_name  = serializers.CharField(source="district_id.name", read_only=True)
    city_name      = serializers.CharField(source="city_id.name", read_only=True)
    zone_name      = serializers.CharField(source="zone_id.name", read_only=True)

    class Meta:
        model = Ward
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def validate(self, attrs):
        validator = unique_name_validator(
            Model=Ward,
            scope_fields=[
                "continent_id",
                "country_id",
                "state_id",
                "district_id",
                "city_id",
                "zone_id",
            ],
        )
        validator(self, attrs)
        return attrs
