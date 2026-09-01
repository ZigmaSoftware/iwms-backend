from rest_framework import serializers
from app.utils.common_audit import CommonAudit


class CommonAuditSerializer(serializers.ModelSerializer):

    scope_label = serializers.CharField(source="get_scope_display", read_only=True)

    # Rows written before tenancy capture existed have no company/project and
    # no actor id. Surface that explicitly instead of rendering blank cells.
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CommonAudit
        fields = "__all__"
        # Identity and tenancy are stamped server-side in perform_create and
        # must never be accepted from the client, or the trail is forgeable.
        read_only_fields = (
            "uuid",
            "createdAt",
            "createdBy",
            "created_by_id",
            "created_by_name",
            "created_by_type",
            "scope",
            "company_unique_id",
            "company_name",
            "project_unique_id",
            "project_name",
        )

    def get_company_name(self, obj):
        if obj.company_name:
            return obj.company_name
        return "Platform" if obj.scope == CommonAudit.Scope.PLATFORM else None

    def get_project_name(self, obj):
        return obj.project_name or None

    def get_created_by_name(self, obj):
        # Fall back to the legacy createdBy username for historical rows.
        return obj.created_by_name or obj.createdBy or None
