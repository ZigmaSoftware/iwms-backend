from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.trip_today_serializer import (
    MyTripTodaySerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    find_active_assignment_for_operator,
    resolve_operator_staff,
)


class MyTripTodayViewSet(viewsets.ViewSet):
    """GET /api/v1/operator-mobile/my-trip-today/"""

    permission_classes = [IsOperatorRole]

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
            assignment = find_active_assignment_for_operator(operator)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        data = MyTripTodaySerializer(assignment).data
        return Response(data, status=status.HTTP_200_OK)


class MyTripsTodayViewSet(viewsets.ViewSet):
    """GET /api/v1/operator-mobile/my-trips-today/

    All of this operator's trips today (bin + household + bulk), for the
    header carousel — unlike `my-trip-today/` (singular), which only returns
    the first match. Trip lifecycle (explicit start/end, re-trip requests)
    is not ported yet, so this only surfaces today's assignments as-is; see
    `iwms-private-vs-government-divergence` memory for why.
    """

    permission_classes = [IsOperatorRole]

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        today = timezone.localdate()
        base = (
            DailyTripAssignment.objects
            .filter(trip_date=today, is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related(
                "panchayat_id",
                "vehicle_id",
                "staff_template_id",
                "staff_template_id__driver_id",
                "staff_template_id__operator_id",
            )
            .prefetch_related("waste_types")
        )

        assignments = list(base.filter(staff_template_id__operator_id=operator))
        if not assignments:
            for candidate in base:
                extras = getattr(candidate.staff_template_id, "extra_operator_id", None) or []
                if operator.staff_unique_id in extras:
                    assignments.append(candidate)

        data = MyTripTodaySerializer(assignments, many=True).data
        return Response({"results": data}, status=status.HTTP_200_OK)
