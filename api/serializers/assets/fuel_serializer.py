from rest_framework import serializers
from ...apps.fuel import Fuel

class FuelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fuel
        fields = '__all__'
