from datetime import date

from rest_framework import viewsets, status
from rest_framework.response import Response

from api.apps.assignment import DailyAssignment
from api.serializers.desktopView.assignments.assignment_serializer import DailyAssignmentSerializer


class DailyAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = DailyAssignmentSerializer
    queryset = DailyAssignment.objects.filter(is_active=True)
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = super().get_queryset()
        driver_id = self.request.query_params.get("driver_id")
        operator_id = self.request.query_params.get("operator_id")
        ward_id = self.request.query_params.get("ward_id")
        for_date = self.request.query_params.get("date")

        if driver_id:
            qs = qs.filter(driver__unique_id=driver_id)
        if operator_id:
            qs = qs.filter(operator__unique_id=operator_id)
        if ward_id:
            qs = qs.filter(ward__unique_id=ward_id)
        if for_date:
            try:
                parts = [int(p) for p in for_date.split("-")]
                qs = qs.filter(date=date(parts[0], parts[1], parts[2]))
            except Exception:
                pass

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        assigned_by = None
        user = getattr(self.request, "user", None)
        if user and user.is_authenticated:
            assigned_by = user
        serializer.save(assigned_by=assigned_by)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
