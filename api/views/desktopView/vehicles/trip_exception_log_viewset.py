from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from api.apps.trip_exception_log import TripExceptionLog
from api.serializers.desktopView.vehicles.trip_exception_log_serializer import (
    TripExceptionLogSerializer
)


class TripExceptionLogViewSet(ModelViewSet):
    """
    Append-only exception logger.
    Used by system automations and supervisors.
    """

    queryset = TripExceptionLog.objects.all()
    serializer_class = TripExceptionLogSerializer
    permission_resource = "TripExceptionLog"
    swagger_tags = ["Desktop / Trip Exceptions"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save()

        return Response(
            TripExceptionLogSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Trip exception logs are immutable"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Trip exception logs cannot be deleted"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
