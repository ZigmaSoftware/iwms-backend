from rest_framework import viewsets
from api.apps.continent import Continent
from api.serializers.desktopView.geography.continent_serializer import ContinentSerializer


class ContinentViewSet(viewsets.ModelViewSet):
    queryset = Continent.objects.filter(is_active=True)
    serializer_class = ContinentSerializer
