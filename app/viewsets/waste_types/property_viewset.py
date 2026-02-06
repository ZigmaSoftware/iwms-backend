from rest_framework import viewsets
from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from app.models.waste_types.property import Property
from app.serializers.waste_types.property_serializer import PropertySerializer


class PropertyViewSet(TenantModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
