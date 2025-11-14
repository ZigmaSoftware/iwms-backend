from rest_framework import viewsets
from api.apps.vehicleCreation import VehicleCreation
from api.serializers.desktopView.vehicles.vehiclecreation_serializer import VehicleCreationSerializer

class VehicleCreationViewSet(viewsets.ModelViewSet):
    queryset = VehicleCreation.objects.filter(is_deleted=False)
    serializer_class = VehicleCreationSerializer
