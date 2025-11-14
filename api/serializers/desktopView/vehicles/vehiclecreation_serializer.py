from rest_framework import serializers
from api.apps.vehicleCreation import VehicleCreation

class VehicleCreationSerializer(serializers.ModelSerializer):
    vehicle_type_name = serializers.CharField(source='vehicle_type.vehicleType', read_only=True)
    fuel_type_name = serializers.CharField(source='fuel_type', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    ward_name = serializers.CharField(source='ward.name', read_only=True)

    class Meta:
        model = VehicleCreation
        fields = "__all__"
