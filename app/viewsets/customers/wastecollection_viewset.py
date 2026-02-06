from rest_framework import viewsets
from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from app.models.customers.wastecollection import WasteCollection
from app.serializers.customers.wastecollection_serializer import WasteCollectionSerializer

class WasteCollectionViewSet(TenantModelViewSet):
    queryset = WasteCollection.objects.filter(is_deleted=False).select_related(
        "customer__ward","customer__zone","customer__city",
        "customer__district","customer__state","customer__country",
        "customer__property_ref","customer__sub_property"
    ).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"
