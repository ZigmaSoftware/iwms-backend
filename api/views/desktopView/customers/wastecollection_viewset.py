from rest_framework import viewsets
from api.apps.wastecollection import WasteCollection
from api.serializers.desktopView.customers.wastecollection_serializer import WasteCollectionSerializer

class WasteCollectionViewSet(viewsets.ModelViewSet):
    queryset = WasteCollection.objects.filter(is_deleted=False).select_related(
        "customer__ward","customer__zone","customer__city",
        "customer__district","customer__state","customer__country",
        "customer__property","customer__sub_property"
    ).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"
