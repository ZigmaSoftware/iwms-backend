from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from api.apps.bin_load_log import BinLoadLog
from api.serializers.desktopView.vehicles.bin_load_log_serializer import (
    BinLoadLogSerializer
)


class BinLoadLogViewSet(ModelViewSet):
    """
    Source-of-truth for load measurement events.
    Used for trip triggering (system-driven).
    """

    queryset = BinLoadLog.objects.all()
    serializer_class = BinLoadLogSerializer
    permission_resource = "BinLoadLog"
    swagger_tags = ["Desktop / Assets"]

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.trigger_trip_instance()

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion of load logs is not allowed"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
