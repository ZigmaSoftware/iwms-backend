from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin

from app.models.superadmin.audits.loginAudit import LoginAudit


class LoginAuditSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    used_hours = serializers.CharField(read_only=True)
    logout_type_display = serializers.CharField(
        source="get_logout_type_display", read_only=True
    )
    # failed | active | manual | idle_timeout | token_expired — one value the
    # list can filter on (matches the viewset's ?session_state= filter).
    session_state = serializers.SerializerMethodField()

    class Meta:
        model = LoginAudit
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "user_unique_id",
            "username",
            "password",
            "ip_address",
            "user_agent",
            "success",
            "reason",
            "timestamp",
            "last_activity_at",
            "logout_at",
            "logout_type",
            "logout_type_display",
            "session_state",
            "session_duration_seconds",
            "used_hours",
            "idle_timeout_seconds",
        ]
        read_only_fields = [
            "unique_id",
            "timestamp",
            "last_activity_at",
            "logout_at",
            "logout_type",
            "session_duration_seconds",
            "idle_timeout_seconds",
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": False, "allow_null": True},
        }

    def get_session_state(self, obj):
        if not obj.success:
            return "failed"
        if obj.logout_at is None:
            return "active"
        return obj.logout_type
