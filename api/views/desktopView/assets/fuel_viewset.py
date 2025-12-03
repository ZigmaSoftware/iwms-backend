from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from api.apps.fuel import Fuel
from api.serializers.desktopView.assets.fuel_serializer import FuelSerializer


class FuelViewSet(viewsets.ModelViewSet):
    queryset = Fuel.objects.filter(is_deleted=False)
    serializer_class = FuelSerializer
    lookup_field = "unique_id"

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())

        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj
