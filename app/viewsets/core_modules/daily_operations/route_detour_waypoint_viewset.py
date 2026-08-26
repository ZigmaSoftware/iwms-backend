from rest_framework import filters

from app.models.schedule_masters.route_detour_waypoint import RouteDetourWaypoint
from app.serializers.core_modules.daily_operations.route_detour_waypoint_serializer import (
    RouteDetourWaypointSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class RouteDetourWaypointViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """CRUD for manual detour waypoints on one trip's Static Route Map.

    No company_id/project_id on the model — tenancy is entirely derived
    from the parent DailyTripAssignment, so CompanyScopedViewSet's scoping
    checks are no-ops here; it's reused only for consistent permission and
    audit-log plumbing.
    """

    serializer_class = RouteDetourWaypointSerializer
    lookup_field = "unique_id"
    http_method_names = ["get", "post", "delete"]

    permission_resource = "RouteDetourWaypoint"

    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["after_stop_id", "sequence"]

    AUDIT_MODULE = "schedule-operations"
    AUDIT_ENDPOINT = "route-detour-waypoint"

    def get_queryset(self):
        queryset = RouteDetourWaypoint.objects.filter(
            is_deleted=False, is_active=True,
        ).order_by("after_stop_id", "sequence")

        assignment_id = self.request.query_params.get("trip_assignment_id")
        if assignment_id:
            queryset = queryset.filter(trip_assignment_id__unique_id=assignment_id)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
