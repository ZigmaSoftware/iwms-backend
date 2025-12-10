from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from api.apps.vehicleTypeCreation import VehicleTypeCreation
from api.serializers.desktopView.vehicles.vehicletypecreation_serializer import VehicleTypeCreationSerializer


class VehicleTypeCreationViewSet(viewsets.ModelViewSet):
    queryset = VehicleTypeCreation.objects.filter(is_deleted=False)
    serializer_class = VehicleTypeCreationSerializer
    lookup_field = "unique_id"

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())

        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj
