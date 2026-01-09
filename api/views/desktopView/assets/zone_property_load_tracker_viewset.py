from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status

from api.apps.zone_property_load_tracker import ZonePropertyLoadTracker
from api.serializers.desktopView.assets.zone_property_load_tracker_serializer import (ZonePropertyLoadTrackerSerializer)


class ZonePropertyLoadTrackerViewSet(ModelViewSet):
    """
    Live load tracking per zone/property/vehicle.
    Used by system & supervisors.
    """

    queryset = ZonePropertyLoadTracker.objects.all()
    serializer_class = ZonePropertyLoadTrackerSerializer
    permission_resource = "ZonePropertyLoadTracker"
    swagger_tags = ["Desktop / Vehicles"]

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion not allowed. Tracker is system-managed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
