from rest_framework import viewsets, status
from rest_framework.response import Response
from api.apps.bin import Bin
from api.serializers.desktopView.masters.bin_serializer import BinSerializer


class BinViewSet(viewsets.ModelViewSet):
    serializer_class = BinSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        """
        Default: only non-deleted bins
        """
        return Bin.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        """
        Soft delete only
        """
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        """
        Return enterprise-friendly response
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Bin successfully decommissioned"},
            status=status.HTTP_204_NO_CONTENT,
        )
