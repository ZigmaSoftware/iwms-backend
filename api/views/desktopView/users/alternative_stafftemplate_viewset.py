from rest_framework import viewsets, status
from rest_framework.response import Response

from api.apps.alternative_staff_template import AlternativeStaffTemplate
from api.serializers.desktopView.users.alternative_stafftemplate_serializer import (
    AlternativeStaffTemplateSerializer
)


class AlternativeStaffTemplateViewSet(viewsets.ModelViewSet):
    """
    API Contract:
    - Create alternative staff mapping
    - Approve / Reject mapping
    - Filter by status, date, template
    """

    queryset = AlternativeStaffTemplate.objects.all()
    serializer_class = AlternativeStaffTemplateSerializer

    # 🔒 CRITICAL: single source of truth for middleware
    permission_resource = "AlternativeStaffTemplate"

    def get_queryset(self):
        qs = super().get_queryset()

        staff_template = self.request.query_params.get("staff_template")
        approval_status = self.request.query_params.get("approval_status")
        effective_date = self.request.query_params.get("effective_date")

        if staff_template:
            qs = qs.filter(staff_template_id=staff_template)

        if approval_status:
            qs = qs.filter(approval_status=approval_status)

        if effective_date:
            qs = qs.filter(effective_date=effective_date)

        return qs.select_related(
            "staff_template",
            "driver",
            "operator",
            "requested_by",
            "approved_by",
        )

    def perform_create(self, serializer):
        serializer.save(
            approval_status="PENDING",
            requested_by=self.request.user,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.approval_status == "APPROVED":
            return Response(
                {"detail": "Approved records cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)
