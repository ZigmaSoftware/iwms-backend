from rest_framework import status, viewsets
from rest_framework.response import Response

from api.apps.route_run import RouteRun
from api.serializers.desktopView.routes.route_run_serializer import (
    RouteRunSerializer,
)


class RouteRunViewSet(viewsets.ModelViewSet):
    """
    Create/list RouteRuns. RouteStops are copied in sequence_no order.
    """

    serializer_class = RouteRunSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = RouteRun.objects.filter(is_deleted=False)
        route_id = self.request.query_params.get("route_id")
        if route_id:
            qs = qs.filter(route_id=route_id)
        return qs.select_related(
            "staff_template",
            "vehicle_type",
            "vehicle",
        ).prefetch_related("stops__route_stop")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
