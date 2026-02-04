from rest_framework import viewsets
from api.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from api.models.assets.property import Property
from api.serializers.desktop.assets.property_serializer import PropertySerializer


class PropertyViewSet(TenantModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
