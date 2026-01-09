from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from api.apps.trip_instance import TripInstance
from api.serializers.desktopView.vehicles.trip_instance_serializer import (
    TripInstanceSerializer
)


class TripInstanceViewSet(ModelViewSet):
    """
    Transport trip execution.
    Created ONLY by system logic.
    """

    queryset = TripInstance.objects.all()
    serializer_class = TripInstanceSerializer
    permission_resource = "TripInstance"
    swagger_tags = ["Desktop / Vehicles"]

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Trip instances are created by system only"},
            status=status.HTTP_403_FORBIDDEN
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Trip instances cannot be deleted"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
