from rest_framework import serializers

from app.models.superadmin.audits.staff_template_audit_log import StaffTemplateAuditLog


class StaffTemplateAuditLogSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    performed_by_name = serializers.SerializerMethodField()

    def get_company_name(self, obj):
        return getattr(obj.company, "name", None)

    def get_project_name(self, obj):
        return getattr(obj.project, "name", None)

    def get_performed_by_name(self, obj):
        return getattr(obj.performed_by_staff, "employee_name", None)

    class Meta:
        model = StaffTemplateAuditLog
        fields = [
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "unique_id",
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
