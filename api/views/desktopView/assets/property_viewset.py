from rest_framework import viewsets
from api.views.tenant_viewset import TenantModelViewSet
from api.apps.property import Property
from api.serializers.desktopView.assets.property_serializer import PropertySerializer


class PropertyViewSet(TenantModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
