from rest_framework import filters, status
from rest_framework.response import Response

from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_static_route import TripPlanStaticRoute
from app.serializers.core_modules.schedule_setup.trip_plan_static_route_serializer import (
    TripPlanStaticRouteSerializer,
)
from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog
from app.services.static_route import save_plan_static_route
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet


class TripPlanStaticRouteViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """Saved static routes of trip plans ("Save Route" on the Static Route
    Map).

    POST {"trip_plan_id": ...} stores the plan's route as currently drawn —
    stops, detours and road path — and copies it to the plan's daily trips
    from today on that haven't finished. Detour and trip plan edits already
    do this automatically (sync_plan_static_route); this is the manual
    "Save Route". There is nothing else to write: every field is built from
    the plan.

    No company_id/project_id on the model — tenancy comes from the parent
    TripPlan, looked up through the tenant scoping on save. Reused for
    consistent permission and audit-log plumbing, like
    RouteDetourWaypointViewSet.
    """

    serializer_class = TripPlanStaticRouteSerializer
    lookup_field = "unique_id"
    http_method_names = ["get", "post"]

    permission_resource = "TripPlanStaticRoute"

    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["trip_plan_id", "saved_at"]

    AUDIT_MODULE = "schedule-operations"
    AUDIT_ENDPOINT = "trip-plan-static-route"

    def get_queryset(self):
        queryset = TripPlanStaticRoute.objects.filter(is_deleted=False, is_active=True)
        trip_plan_id = self.request.query_params.get("trip_plan_id")
        if trip_plan_id:
            queryset = queryset.filter(trip_plan_id=trip_plan_id)
        return queryset

    def create(self, request, *args, **kwargs):
        trip_plan_id = request.data.get("trip_plan_id")
        if not trip_plan_id:
            return Response(
                {"trip_plan_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = self._scope_to_tenant(
            TripPlan.objects.filter(unique_id=trip_plan_id, is_deleted=False)
        ).first()
        if not plan:
            return Response(
                {"detail": "Trip Plan was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        previous = TripPlanStaticRoute.objects.filter(trip_plan_id=plan.unique_id).first()
        previous_data = self._serialize_instance(previous) if previous else None
        try:
            saved, routing_error, updated_trips = save_plan_static_route(
                plan,
                user_id=self._audit_actor_id(),
                trigger=StaticRouteAuditLog.TRIGGER_MANUAL_SAVE,
            )
        except Exception as exc:
            self._log_failed_audit(exc, instance=previous, new_data=request.data)
            raise
        self.log_audit(
            request,
            instance=saved,
            previous_data=previous_data,
            new_data=self._serialize_instance(saved),
        )
        return Response(
            {
                **self.get_serializer(saved).data,
                "routing_error": routing_error,
                "updated_trip_count": updated_trips,
            },
            status=status.HTTP_201_CREATED,
        )
