from rest_framework import viewsets

from api.apps.staff_template_audit_log import StaffTemplateAuditLog
from api.serializers.desktopView.users.staff_template_audit_log_serializer import (
    StaffTemplateAuditLogSerializer,
)


class StaffTemplateAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only audit trail for staff template workflows.
    """

    serializer_class = StaffTemplateAuditLogSerializer
    lookup_field = "id"

    def get_queryset(self):
        qs = StaffTemplateAuditLog.objects.select_related("performed_by")

        entity_type = self.request.query_params.get("entity_type")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)

        entity_id = self.request.query_params.get("entity_id")
        if entity_id:
            qs = qs.filter(entity_id=entity_id)

        action = self.request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)

        performed_role = self.request.query_params.get("performed_role")
        if performed_role:
            qs = qs.filter(performed_role=performed_role)

        performed_by = self.request.query_params.get("performed_by")
        if performed_by:
            qs = qs.filter(performed_by__unique_id=performed_by)

        return qs
