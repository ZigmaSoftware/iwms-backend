from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.user_creations.loginAudit import LoginAudit
from app.serializers.audits.login_audit_serializer import LoginAuditSerializer
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)


class LoginAuditViewSet(CompanyScopedViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginAuditSerializer
    permission_resource = "LoginAudit"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]

    def get_queryset(self):
        return (
            LoginAudit.objects
            .select_related("company_id", "project_id")
            .order_by("-timestamp")
        )
