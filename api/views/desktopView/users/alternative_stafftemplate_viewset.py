from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import NotAuthenticated

from api.apps.alternative_staff_template import AlternativeStaffTemplate
from api.apps.userCreation import User
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

    def _resolve_request_user(self):
        user = getattr(self.request, "user", None)
        if user and not getattr(user, "is_anonymous", False):
            return user

        raw_request = getattr(self.request, "_request", None)
        raw_user = getattr(raw_request, "user", None) if raw_request else None
        if raw_user and not getattr(raw_user, "is_anonymous", False):
            return raw_user

        payload = getattr(self.request, "jwt_payload", None) or getattr(raw_request, "jwt_payload", None)
        unique_id = payload.get("unique_id") if isinstance(payload, dict) else None
        if unique_id:
            return User.objects.filter(unique_id=unique_id).first()

        return None

    def perform_create(self, serializer):
        user = self._resolve_request_user()
        if not user:
            raise NotAuthenticated("Authentication required")
        serializer.save(
            approval_status="PENDING",
            requested_by=user,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.approval_status == "APPROVED":
            return Response(
                {"detail": "Approved records cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)
