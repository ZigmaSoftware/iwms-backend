from rest_framework import viewsets
from ...apps.continent import Continent
from ...serializers.geography.continent_serializer import ContinentSerializer


class ContinentViewSet(viewsets.ModelViewSet):
    queryset = Continent.objects.filter(is_active=True)
    serializer_class = ContinentSerializer
