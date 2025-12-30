from rest_framework import status, viewsets
from rest_framework.response import Response

from api.apps.route_stop import RouteStop
from api.serializers.desktopView.routes.route_stop_serializer import (
    RouteStopSerializer,
)


class RouteStopViewSet(viewsets.ModelViewSet):
    """
    Manage RouteStop records for route templates.
    stop_type is derived from property/sub_property automatically.
    """

    serializer_class = RouteStopSerializer
    queryset = RouteStop.objects.filter(is_deleted=False)

    def get_queryset(self):
        qs = self.queryset
        route_id = self.request.query_params.get("route_id")
        if route_id:
            qs = qs.filter(route_id=route_id)
        return qs.select_related(
            "ward",
            "zone",
            "property",
            "sub_property",
            "customer",
        ).order_by("sequence_no", "id")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
