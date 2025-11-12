from rest_framework import viewsets
from ...apps.vehicleTypeCreation import VehicleTypeCreation
from ...serializers.vehicles.vehicletypecreation_serializer import VehicleTypeCreationSerializer

class VehicleTypeCreationViewSet(viewsets.ModelViewSet):
    queryset = VehicleTypeCreation.objects.filter(is_delete=False)
    serializer_class = VehicleTypeCreationSerializer
