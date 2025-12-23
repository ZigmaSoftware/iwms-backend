from rest_framework import viewsets
from api.apps.bin import Bin
from api.serializers.desktopView.masters.bin_serializer import BinSerializer


class BinViewSet(viewsets.ModelViewSet):
    queryset = Bin.objects.filter(is_deleted=False)
    serializer_class = BinSerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
