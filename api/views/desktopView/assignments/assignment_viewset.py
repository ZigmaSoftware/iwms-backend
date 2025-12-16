from datetime import date
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from api.apps.assignment import DailyAssignment
from api.serializers.desktopView.assignments.assignment_serializer import (
    DailyAssignmentSerializer,
)


class DailyAssignmentViewSet(viewsets.ModelViewSet):

    serializer_class = DailyAssignmentSerializer
    queryset = DailyAssignment.objects.filter(is_active=True)
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        if "driver_id" in params:
            qs = qs.filter(driver__unique_id=params["driver_id"])

        if "operator_id" in params:
            qs = qs.filter(operator__unique_id=params["operator_id"])

        if "ward_id" in params:
            qs = qs.filter(ward__unique_id=params["ward_id"])

        if "shift" in params:
            qs = qs.filter(shift=params["shift"])

        if "assignment_type" in params:
            qs = qs.filter(assignment_type=params["assignment_type"])

        if "date" in params:
            qs = qs.filter(date=params["date"])
        else:
            qs = qs.filter(date=date.today())

        return qs.order_by("shift")

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(assigned_by=user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # 🔒 CANCEL ASSIGNMENT (AUTH REQUIRED)
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def cancel(self, request, unique_id=None):
        assignment = self.get_object()

        reason = request.data.get("reason")
        if not reason:
            return Response(
                {"reason": "Cancellation reason is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.is_active = False
        assignment.cancelled_reason = reason
        assignment.cancelled_by = request.user
        assignment.cancelled_at = timezone.now()

        assignment.save(
            update_fields=[
                "is_active",
                "cancelled_reason",
                "cancelled_by",
                "cancelled_at",
            ]
        )

        return Response(
            {"status": "cancelled"},
            status=status.HTTP_200_OK,
        )
