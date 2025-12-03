from rest_framework import serializers
from api.apps.district import District

class DistrictSerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source='continent_id.name', read_only=True)
    country_name   = serializers.CharField(source='country_id.name', read_only=True)
    state_name     = serializers.CharField(source='state_id.name', read_only=True)

    class Meta:
        model = District
        fields = "__all__"
        read_only_fields = ["unique_id"]
