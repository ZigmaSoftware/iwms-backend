from rest_framework import viewsets, status
from rest_framework.response import Response
from api.apps.stafftemplate import StaffTemplate
from api.serializers.desktopView.users.stafftemplate_serializer import (
    StaffTemplateSerializer
)


class StaffTemplateViewSet(viewsets.ModelViewSet):
    """
    Staff Template API
    - Soft delete enforced
    - ERP-safe partial updates
    """

    serializer_class = StaffTemplateSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = StaffTemplate.objects.filter(is_deleted=False)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        return qs.select_related(
            "primary_driver_id",
            "secondary_driver_id",
            "primary_operator_id",
            "secondary_operator_id",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": "Staff template soft-deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True  # critical for ERP ops
        return super().update(request, *args, **kwargs)
