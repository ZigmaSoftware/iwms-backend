from rest_framework import status, viewsets
from rest_framework.response import Response

from app.permissions.operator_permission import IsOperatorOrDriverRole
from app.serializers.operator_mobile.trip_today_serializer import (
    MyTripTodaySerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    find_active_assignment_for_staff,
    resolve_operator_staff,
)


class MyTripTodayViewSet(viewsets.ViewSet):
    """GET /api/v1/operator-mobile/my-trip-today/

    Returns today's single active trip for the authenticated staff. Works for
    both operators and drivers — the assignment is resolved against the staff
    template's operator_id or driver_id depending on the caller's role, so a
    paired operator + driver on the same template see the same trip.
    """

    permission_classes = [IsOperatorOrDriverRole]

    def list(self, request):
        try:
            staff = resolve_operator_staff(request.user)
            assignment = find_active_assignment_for_staff(staff)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        data = MyTripTodaySerializer(assignment, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)
