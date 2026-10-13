from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin

from app.models.superadmin.audits.auditlog import AuditLog


class AuditLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "user_id",
            "staffusertype_id",
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id",
            "success",
            "reason",
            "ip_address",
            "user_agent",
            "timestamp",
        ]
        read_only_fields = ["unique_id", "timestamp"]
