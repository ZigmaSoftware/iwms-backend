from rest_framework import viewsets, status
from rest_framework.response import Response
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
