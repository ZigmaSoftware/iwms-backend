from rest_framework import viewsets
from api.apps.vehicleTypeCreation import VehicleTypeCreation
from api.serializers.desktopView.vehicles.vehicletypecreation_serializer import VehicleTypeCreationSerializer

class VehicleTypeCreationViewSet(viewsets.ModelViewSet):
    queryset = VehicleTypeCreation.objects.filter(is_delete=False)
    serializer_class = VehicleTypeCreationSerializer
