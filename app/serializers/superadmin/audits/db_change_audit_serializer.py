from rest_framework import serializers

from app.models.superadmin.audits.db_change_audit import DbChangeAudit
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class DbChangeAuditSerializer(serializers.ModelSerializer):
    """List view of a direct database change: which table and row, what
    kind of change, which DB login made it and when. The row snapshots are
    left out — see the detail serializer. Name lookups are memoised per
    serializer instance, like the static route audit."""

    operation_label = serializers.CharField(source="get_operation_display", read_only=True)
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = DbChangeAudit
        fields = [
            "id",
            "table_name",
            "operation",
            "operation_label",
            "object_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "changed_columns",
            "db_user",
            "db_account",
            "connection_id",
            "changed_at",
        ]
        read_only_fields = fields

    def _lookup(self, model, value):
        if not value:
            return None
        cache = self.__dict__.setdefault("_name_cache", {})
        key = (model, value)
        if key not in cache:
            cache[key] = (
                model.objects.filter(unique_id=value).values_list("name", flat=True).first()
            )
        return cache[key]

    def get_company_name(self, obj):
        return self._lookup(Company, obj.company_id)

    def get_project_name(self, obj):
        return self._lookup(Project, obj.project_id)


class DbChangeAuditDetailSerializer(DbChangeAuditSerializer):
    """One change in full: the row before and after."""

    class Meta(DbChangeAuditSerializer.Meta):
        fields = DbChangeAuditSerializer.Meta.fields + ["old_data", "new_data"]
        read_only_fields = fields
