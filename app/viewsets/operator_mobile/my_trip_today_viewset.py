from rest_framework import status, viewsets
from rest_framework.response import Response

from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.trip_today_serializer import (
    MyTripTodaySerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    find_assignments_for_operator_today,
    find_active_assignment_for_operator,
    resolve_operator_staff,
)
from app.services.daily_service_notice import notices_for_staff, serialize_notice
from django.utils import timezone


class MyTripTodayViewSet(viewsets.ViewSet):
    """GET /api/v1/operator-mobile/my-trip-today/"""

    permission_classes = [IsOperatorRole]
    permission_resource = "DailyTripAssignment"

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
            assignment = find_active_assignment_for_operator(operator)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        data = MyTripTodaySerializer(assignment, context={"request": request}).data
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
    permission_resource = "DailyTripAssignment"

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        # Driver ("captain") and operator apps are merged, so match either
        # slot on the staff template — same rule as
        # helpers.find_active_assignment_for_operator.
        assignments = find_assignments_for_operator_today(operator)

        data = MyTripTodaySerializer(
            assignments, many=True, context={"request": request}
        ).data
        notices = [
            serialize_notice(notice)
            for notice in notices_for_staff(operator, timezone.localdate())
        ]
        return Response(
            {"results": data, "service_notices": notices},
            status=status.HTTP_200_OK,
        )
