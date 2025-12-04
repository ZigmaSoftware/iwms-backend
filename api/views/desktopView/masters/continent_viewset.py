from rest_framework import viewsets
from api.apps.continent import Continent
from api.serializers.desktopView.masters.continent_serializer import ContinentSerializer

class ContinentViewSet(viewsets.ModelViewSet):
    queryset = Continent.objects.filter(is_deleted=False)
    serializer_class = ContinentSerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
