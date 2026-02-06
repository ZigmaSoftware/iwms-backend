from rest_framework import viewsets
from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from app.models.waste_types.subproperty import SubProperty
from app.serializers.waste_types.subproperty_serializer import SubPropertySerializer

class SubPropertyViewSet(TenantModelViewSet):
    queryset = SubProperty.objects.filter(is_deleted=False)\
        .select_related("property_id")\
        .order_by("sub_property_name")

    serializer_class = SubPropertySerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
