from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin

from api.apps.staff_template_audit_log import StaffTemplateAuditLog


class StaffTemplateAuditLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    performed_by = serializers.SlugRelatedField(
        slug_field="unique_id",
        read_only=True,
    )
    performed_by_name = serializers.CharField(
        source="performed_by.staff_id.employee_name",
        read_only=True,
    )

    class Meta:
        model = StaffTemplateAuditLog
        fields = [
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "id",
            "entity_type",
            "entity_id",
            "action",
            "performed_by",
            "performed_by_name",
            "performed_role",
            "change_remarks",
            "performed_at",
        ]
        read_only_fields = fields
