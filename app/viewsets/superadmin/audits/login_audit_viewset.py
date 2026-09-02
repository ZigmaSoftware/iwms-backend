from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.staff_creations.loginAudit import LoginAudit
from app.serializers.superadmin.audits.login_audit_serializer import LoginAuditSerializer
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage


class LoginAuditViewSet(CompanyScopedViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginAuditSerializer
    permission_resource = "LoginAudit"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    pagination_class = LimitOffsetWithPage

    def get_queryset(self):
        return (
            LoginAudit.objects
            .select_related("company_id", "project_id")
            .order_by("-timestamp")
        )
