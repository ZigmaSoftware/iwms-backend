from rest_framework import serializers
from ...apps.district import District

class DistrictSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)

    class Meta:
        model = District
        fields = '__all__'
