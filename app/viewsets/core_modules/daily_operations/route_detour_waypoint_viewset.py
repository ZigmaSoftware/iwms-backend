from rest_framework import filters

from app.models.core_modules.daily_operations.route_detour_waypoint import RouteDetourWaypoint
from app.serializers.core_modules.daily_operations.route_detour_waypoint_serializer import (
    RouteDetourWaypointSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet


class RouteDetourWaypointViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """CRUD for manual detour waypoints on a trip plan's static route (the
    Static Route Map's Trip Plan mode). Every change re-saves the plan's
    route and passes it to the plan's unfinished daily trips.

    No company_id/project_id on the model — tenancy is entirely derived
    from the parent TripPlan / DailyTripAssignment, so CompanyScopedViewSet's scoping
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

        trip_plan_id = self.request.query_params.get("trip_plan_id")
        if trip_plan_id:
            queryset = queryset.filter(trip_plan_id=trip_plan_id)

        assignment_id = self.request.query_params.get("trip_assignment_id")
        if assignment_id:
            queryset = queryset.filter(trip_assignment_id=assignment_id)

        return queryset

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_plan_route(serializer.instance.trip_plan_id)

    def perform_destroy(self, instance):
        trip_plan_id = instance.trip_plan_id
        instance.delete()
        self._sync_plan_route(trip_plan_id)

    def _sync_plan_route(self, trip_plan_id):
        """A detour on a trip plan changes its static route: store the new
        route and pass it to the plan's unfinished daily trips right away."""
        if not trip_plan_id:
            return
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        from app.services.static_route import sync_plan_static_route

        plan = TripPlan.objects.filter(unique_id=trip_plan_id, is_deleted=False).first()
        if plan:
            sync_plan_static_route(plan, user_id=self._audit_actor_id())
