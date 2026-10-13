from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.models.superadmin.audits.auditlog import AuditLog
from app.serializers.superadmin.audits.audit_log_serializer import AuditLogSerializer


class AuditLogViewSet(CompanyScopedViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = AuditLogSerializer
    permission_resource = "AuditLog"

    def get_queryset(self):
        return AuditLog.objects.order_by("-timestamp")
