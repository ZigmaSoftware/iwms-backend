from rest_framework import viewsets
from api.apps.fuel import Fuel
from api.serializers.desktopView.assets.fuel_serializer import FuelSerializer


class FuelViewSet(viewsets.ModelViewSet):
    queryset = Fuel.objects.filter(is_deleted=False)
    serializer_class = FuelSerializer
