from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import NotAuthenticated

from api.apps.userCreation import User
from api.apps.stafftemplate import StaffTemplate
from api.serializers.desktopView.users.stafftemplate_serializer import (
    StaffTemplateSerializer
)


class StaffTemplateViewSet(viewsets.ModelViewSet):
    """
    Staff Template API
    - Status and approval filters
    - ERP-safe partial updates
    """

    serializer_class = StaffTemplateSerializer
    lookup_field = "unique_id"
    permission_resource = "StaffTemplateCreation"

    def get_queryset(self):
        qs = StaffTemplate.objects.all()

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        approval_status = self.request.query_params.get("approval_status")
        if approval_status:
            qs = qs.filter(approval_status=approval_status)

        return qs.select_related(
            "driver_id",
            "operator_id",
            "created_by",
            "updated_by",
            "approved_by",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": "Staff template deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True  # critical for ERP ops
        return super().update(request, *args, **kwargs)

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
        """
        Tie audit fields to the authenticated user so the client
        does not have to post created_by / updated_by.
        """
        user = self._resolve_request_user()
        if not user:
            raise NotAuthenticated("Authentication required")
        serializer.save(
            created_by=user,
            updated_by=user,
            approved_by=serializer.validated_data.get("approved_by"),
        )

    def perform_update(self, serializer):
        user = self._resolve_request_user()
        if not user:
            raise NotAuthenticated("Authentication required")
        serializer.save(
            updated_by=user or serializer.instance.updated_by,
            approved_by=serializer.validated_data.get("approved_by", serializer.instance.approved_by),
        )
