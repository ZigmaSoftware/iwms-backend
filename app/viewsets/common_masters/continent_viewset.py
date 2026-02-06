from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet

from rest_framework import viewsets
from app.models.common_masters.continent import Continent
from app.serializers.common_masters.continent_serializer import ContinentSerializer

class ContinentViewSet(TenantModelViewSet):
    queryset = Continent.objects.filter(is_deleted=False)
    serializer_class = ContinentSerializer
    lookup_field = "unique_id"
    permission_resource = "Continent"

    def perform_destroy(self, instance):
        instance.delete()
