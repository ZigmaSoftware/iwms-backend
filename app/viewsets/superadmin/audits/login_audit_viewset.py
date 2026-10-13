from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.models.superadmin.audits.loginAudit import LoginAudit
from app.serializers.superadmin.audits.login_audit_serializer import LoginAuditSerializer
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage
from app.services.login_session import close_stale_sessions_throttled


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

    def list(self, request, *args, **kwargs):
        # Close sessions nobody logged out of, so rows don't read "Active"
        # long after the token died (works without the cron command).
        close_stale_sessions_throttled()
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = LoginAudit.objects.order_by("-timestamp")
        # ?session_state= active | manual | idle_timeout | token_expired | failed
        state = self.request.query_params.get("session_state")
        if state == "failed":
            queryset = queryset.filter(success=False)
        elif state == "active":
            queryset = queryset.filter(success=True, logout_at__isnull=True)
        elif state in dict(LoginAudit.LOGOUT_TYPE_CHOICES):
            queryset = queryset.filter(success=True, logout_type=state)
        return queryset
