from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from app.models.schedule_masters.trip_delay_report import TripDelayReport
from app.models.notifications.staff_notification import StaffNotification
from app.serializers.core_modules.daily_operations.trip_delay_report_serializer import (
    TripDelayAcknowledgeSerializer,
    TripDelayReportSerializer,
)
from app.services.staff_notification_service import notify_staff
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class TripDelayReportViewSet(CompanyScopedViewSet):
    """Driver-reported trip delays (puncture, traffic, minor repair, ...).

    Deliberately thin compared with VehicleBreakdownViewSet: a delay changes
    nothing about the trip, so there is no vehicle/crew reassignment here —
    only create (driver), list/retrieve (supervisor) and two state nudges.
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = (
        TripDelayReport.objects.select_related(
            "company_id",
            "project_id",
            "trip_assignment_id",
            "trip_assignment_id__vehicle_id",
            "trip_assignment_id__staff_template_id",
            "trip_assignment_id__staff_template_id__driver_id",
            "trip_assignment_id__staff_template_id__operator_id",
            "reported_by",
            "acknowledged_by",
        )
        .filter(is_deleted=False)
    )
    serializer_class = TripDelayReportSerializer
    lookup_field = "unique_id"
    permission_resource = "TripDelayReport"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["created_at", "status", "delay_reason"]

    def perform_create(self, serializer):
        """Stamp the reporter and tenant scope from the request/trip.

        The driver's app sends only the trip, reason and remarks — see the
        serializer's read_only_fields. company/project are filled by the
        model's save() from the assignment.
        """
        from app.models.user_creations.staffcreation import Staffcreation

        user = self.request.user
        reporter = user if isinstance(user, Staffcreation) else None
        instance = serializer.save(reported_by=reporter)
        self._notify_supervisors(instance)

    def _notify_supervisors(self, report):
        """Tell the trip's supervisor a delay was reported.

        Best-effort: a notification failure must never lose the driver's
        report, which is already committed by the time we get here.
        """
        assignment = report.trip_assignment_id
        recipients = []
        supervisor = getattr(assignment, "supervisor_id", None)
        if supervisor is not None:
            recipients.append(supervisor)
        plan_supervisor = getattr(
            getattr(assignment, "trip_plan_id", None), "supervisor_id", None
        )
        if plan_supervisor is not None and plan_supervisor not in recipients:
            recipients.append(plan_supervisor)

        minutes = report.estimated_delay_minutes
        suffix = f" (~{minutes} min)" if minutes else ""
        for staff in recipients:
            try:
                notify_staff(
                    staff,
                    StaffNotification.TYPE_TRIP_DELAY_REPORTED,
                    "Trip delayed",
                    f"{assignment.unique_id} delayed — "
                    f"{report.get_delay_reason_display()}{suffix}. "
                    f"{report.delay_remarks}",
                    data={
                        "event": "trip_delay_reported",
                        "delay_report_id": report.unique_id,
                        "assignment_id": assignment.unique_id,
                        "delay_reason": report.delay_reason,
                    },
                )
            except Exception:  # noqa: BLE001 — see docstring
                continue

    @action(detail=True, methods=["patch"], url_path="acknowledge")
    def acknowledge(self, request, unique_id=None):
        report = self.get_object()
        payload = TripDelayAcknowledgeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        from app.models.user_creations.staffcreation import Staffcreation

        user = request.user
        changed = report.mark_acknowledged(
            by=user if isinstance(user, Staffcreation) else None,
            remarks=payload.validated_data.get("supervisor_remarks"),
        )
        if not changed:
            return Response(
                {
                    "status": "error",
                    "message": "This delay is not awaiting acknowledgement.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["patch"], url_path="resolve")
    def resolve(self, request, unique_id=None):
        report = self.get_object()
        payload = TripDelayAcknowledgeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        changed = report.mark_resolved(
            remarks=payload.validated_data.get("supervisor_remarks"),
        )
        if not changed:
            return Response(
                {"status": "error", "message": "This delay is already resolved."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(report).data)
