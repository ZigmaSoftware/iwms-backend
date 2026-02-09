from app.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from app.models.user_creations.loginAudit import LoginAudit
from app.serializers.audits.login_audit_serializer import LoginAuditSerializer


class LoginAuditViewSet(TenantModelViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginAuditSerializer
    permission_resource = "LoginAudit"

    def get_queryset(self):
        return (
            LoginAudit.objects
            .select_related("company_id", "project_id")
            .order_by("-timestamp")
        )
