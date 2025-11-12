from rest_framework import viewsets
from ...apps.vehicleCreation import VehicleCreation
from ...serializers.vehicles.vehiclecreation_serializer import VehicleCreationSerializer

class VehicleCreationViewSet(viewsets.ModelViewSet):
    queryset = VehicleCreation.objects.filter(is_deleted=False)
    serializer_class = VehicleCreationSerializer
