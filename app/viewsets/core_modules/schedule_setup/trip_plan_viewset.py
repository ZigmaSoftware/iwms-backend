from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.serializers.core_modules.schedule_setup.trip_plan_serializer import (
    TripPlanSerializer,
)
from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog
from app.services.static_route import plan_static_route, sync_plan_static_route
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage
from app.utils.bulk_upload_mixin import BulkUploadMixin


class TripPlanViewSet(BulkUploadMixin, AuditViewSetMixin, CompanyScopedViewSet):
    # Every field above (company_id, staff_template_id, wards, etc.) is now a
    # plain CharField/TextField id column, not a real ForeignKey/M2M, so
    # select_related/prefetch_related can no longer follow them — the
    # serializer resolves each one on demand via its own queries instead.
    queryset = TripPlan.objects.filter(is_deleted=False)

    serializer_class = TripPlanSerializer
    lookup_field = "unique_id"
    swagger_tags = ["Desktop / Operations / Trip Plan"]
    permission_resource = "TripPlan"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    pagination_class = LimitOffsetWithPage
    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "trip-plans"

    @staticmethod
    def permission_action_for_request(request, default_action):
        # Setting or ending a breakdown replacement vehicle changes an
        # existing plan, so it needs "edit", not the POST default "add".
        if request.method == "POST" and "/vehicle-substitution" in request.path:
            return "edit"
        return default_action

    def get_queryset(self):
        qs = super().get_queryset()

        if self._is_supervisor_user():
            qs = qs.filter(supervisor_id=self.request.user.staff_unique_id)

        return qs

    @swagger_auto_schema(request_body=TripPlanSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(request_body=TripPlanSerializer)
    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        # Stops may have changed: keep a saved static route (and the daily
        # trips following it) in step. Plans whose route was never drawn
        # are left alone.
        sync_plan_static_route(
            self.get_object(),
            user_id=self._audit_actor_id(),
            only_if_saved=True,
            trigger=StaticRouteAuditLog.TRIGGER_TRIP_PLAN_EDIT,
        )
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # trip_plan_id is a plain CharField (no reverse accessor), so query directly.
        if DailyTripAssignment.objects.filter(
            trip_plan_id=instance.unique_id, is_deleted=False
        ).exists():
            return Response(
                {"detail": "Trip plans with daily assignments cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="static-route")
    def static_route(self, request, unique_id=None):
        """The plan's static route for the Static Route Map: plant → active
        plan stops in sequence → plant, plus the detours drawn on the plan,
        and what was last saved (see TripPlanStaticRouteViewSet). Daily
        trips generated from this plan get a copy of the saved route."""
        return Response(plan_static_route(self.get_object()))

    # ── Vehicle substitution (breakdown stand-in vehicle) ─────────────
    # While the plan's vehicle is under breakdown its daily trips run on a
    # replacement vehicle with the plan's own crew. Verify & Approve on a
    # breakdown sets these up; these actions let the supervisor add, change
    # or end one later. See app/services/vehicle_substitution.py.

    def _substitution_vehicle(self, plan, vehicle_id):
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation

        return VehicleCreation.objects.filter(
            unique_id=vehicle_id,
            company_id=plan.company_id,
            project_id=plan.project_id,
            is_deleted=False,
            is_active=True,
        ).first()

    @staticmethod
    def _substitution_from_date(raw):
        from datetime import date

        from django.utils import timezone

        today = timezone.localdate()
        if not raw:
            return today, None
        try:
            value = date.fromisoformat(str(raw))
        except ValueError:
            return None, "Use YYYY-MM-DD format."
        if value < today:
            return None, "The start date cannot be in the past."
        return value, None

    @action(detail=True, methods=["get"], url_path="vehicle-substitution-check")
    def vehicle_substitution_check(self, request, unique_id=None):
        """The replacement vehicle's regular work on this plan's days, so the
        supervisor can confirm before saving. ?replacement_vehicle_id=&from_date="""
        from app.services import vehicle_substitution

        plan = self.get_object()
        from_date, error = self._substitution_from_date(request.query_params.get("from_date"))
        if error:
            return Response({"from_date": error}, status=status.HTTP_400_BAD_REQUEST)
        vehicle_id = request.query_params.get("replacement_vehicle_id")
        return Response({
            "clashes": vehicle_substitution.plan_clashes(vehicle_id, plan, from_date) if vehicle_id else [],
            "plan_vehicle_under_breakdown": vehicle_substitution.is_broken_down(plan.vehicle_id),
        })

    @action(detail=True, methods=["post"], url_path="vehicle-substitution")
    def create_vehicle_substitution(self, request, unique_id=None):
        """Body: {replacement_vehicle_id, from_date?, confirm_clashes?}.
        Answers 409 with the clashes until `confirm_clashes` is true."""
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        from app.services import vehicle_substitution

        plan = self.get_object()
        if not vehicle_substitution.is_broken_down(plan.vehicle_id):
            return Response(
                {"detail": "This plan's vehicle is not under breakdown."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from_date, error = self._substitution_from_date(request.data.get("from_date"))
        if error:
            return Response({"from_date": error}, status=status.HTTP_400_BAD_REQUEST)
        vehicle = self._substitution_vehicle(plan, request.data.get("replacement_vehicle_id"))
        if vehicle is None:
            return Response(
                {"replacement_vehicle_id": "Select an active vehicle of this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if vehicle.unique_id == plan.vehicle_id:
            return Response(
                {"replacement_vehicle_id": "Pick a vehicle other than the broken one."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if vehicle.operational_status == VehicleCreation.OperationalStatus.BREAKDOWN:
            return Response(
                {"replacement_vehicle_id": "This vehicle is under breakdown."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        clashes = vehicle_substitution.plan_clashes(vehicle.unique_id, plan, from_date)
        if clashes and str(request.data.get("confirm_clashes", "")).lower() not in {"true", "1"}:
            return Response(
                {
                    "detail": f"{vehicle.vehicle_no} already has regular work on this plan's days.",
                    "clashes": clashes,
                },
                status=status.HTTP_409_CONFLICT,
            )

        substitution = vehicle_substitution.create_substitution(
            plan, vehicle.unique_id, from_date, created_by_id=self._audit_actor_id(),
        )
        return Response(
            {
                **TripPlanSerializer(plan, context={"request": request}).data["vehicle_substitution"],
                "clashes": clashes,
                "created_id": substitution.unique_id,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="vehicle-substitution/end")
    def end_vehicle_substitution(self, request, unique_id=None):
        from app.services import vehicle_substitution

        plan = self.get_object()
        ended = vehicle_substitution.end_substitutions(
            vehicle_substitution.active_substitutions().filter(trip_plan_id=plan.unique_id),
            "Ended by supervisor",
        )
        if not ended:
            return Response(
                {"detail": "This plan has no replacement vehicle."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"ended": ended}, status=status.HTTP_200_OK)
