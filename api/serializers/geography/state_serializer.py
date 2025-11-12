from rest_framework import serializers
from ...apps.state import State

class StateSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)

    class Meta:
        model = State
        fields = '__all__'
