from rest_framework import serializers
from api.apps.state import State

class StateSerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(
        source='continent_id.name',
        read_only=True
    )
    country_name = serializers.CharField(
        source='country_id.name',
        read_only=True
    )
    class Meta:
        model = State
        fields = '__all__'
        read_only_fields = ["unique_id"]
