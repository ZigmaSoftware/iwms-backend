from rest_framework import status, viewsets
from rest_framework.response import Response

from api.apps.daily_route_assignment import DailyRouteAssignment
from api.serializers.desktopView.routes.daily_route_assignment_serializer import (
    DailyRouteAssignmentSerializer,
)


class DailyRouteAssignmentViewSet(viewsets.ModelViewSet):
    """
    Simplified daily assignment binder:
    vehicle type + route + staff template + route run.
    """

    serializer_class = DailyRouteAssignmentSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = DailyRouteAssignment.objects.filter(is_deleted=False)
        route_run_id = self.request.query_params.get("route_run_id")
        if route_run_id:
            qs = qs.filter(route_run__unique_id=route_run_id)
        return qs.select_related(
            "vehicle_type",
            "staff_template",
            "route_run",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
