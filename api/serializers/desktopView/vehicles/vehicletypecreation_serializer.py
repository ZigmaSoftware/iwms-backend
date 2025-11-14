from rest_framework import serializers
from api.apps.vehicleTypeCreation import VehicleTypeCreation

class VehicleTypeCreationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleTypeCreation
        fields = '__all__'
