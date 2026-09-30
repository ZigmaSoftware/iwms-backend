from rest_framework import serializers

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class PermissionAuditLogSerializer(serializers.ModelSerializer):
    """Read-only view of a permission grant change with its ids resolved to
    display names. Lookups are memoised per serializer instance, since a page
    of rows mostly repeats the same few companies, screens and actors."""

    source_label = serializers.CharField(source="get_source_display", read_only=True)
    target_name = serializers.SerializerMethodField()
    app_module_name = serializers.SerializerMethodField()
    column_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    mainscreen_name = serializers.SerializerMethodField()
    userscreen_name = serializers.SerializerMethodField()
    userscreenaction_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PermissionAuditLog
        fields = [
            "id",
            "source",
            "source_label",
            "target_id",
            "target_name",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "mainscreen_id",
            "mainscreen_name",
            "userscreen_id",
            "userscreen_name",
            "userscreenaction_id",
            "userscreenaction_name",
            "app_module_id",
            "app_module_name",
            "column_id",
            "column_name",
            "updated_by",
            "updated_by_name",
            "is_active",
            "is_deleted",
            "previous_is_active",
            "previous_is_deleted",
            "action_type",
            "timestamp",
        ]
        read_only_fields = fields

    def _lookup(self, model, value, field, name_field):
        if not value:
            return None
        cache = self.__dict__.setdefault("_name_cache", {})
        key = (model, value)
        if key not in cache:
            cache[key] = (
                model.objects.filter(**{field: value})
                .values_list(name_field, flat=True)
                .first()
            )
        return cache[key]

    def get_company_name(self, obj):
        return self._lookup(Company, obj.company_id, "unique_id", "name")

    def get_project_name(self, obj):
        return self._lookup(Project, obj.project_id, "unique_id", "name")

    def get_mainscreen_name(self, obj):
        return self._lookup(MainScreen, obj.mainscreen_id, "unique_id", "mainscreen_name")

    def get_userscreen_name(self, obj):
        return self._lookup(UserScreen, obj.userscreen_id, "unique_id", "userscreen_name")

    def get_userscreenaction_name(self, obj):
        return self._lookup(
            UserScreenAction, obj.userscreenaction_id, "unique_id", "action_name"
        )

    def get_target_name(self, obj):
        if obj.source.startswith("STAFF_"):
            return self._lookup(
                Staffcreation, obj.target_id, "staff_unique_id", "employee_name"
            ) or obj.target_id
        if obj.source.startswith("CUSTOMER_"):
            return self._lookup(
                CustomerCreation, obj.target_id, "unique_id", "customer_name"
            ) or obj.target_id
        return None

    def get_app_module_name(self, obj):
        return self._lookup(AppModule, obj.app_module_id, "unique_id", "label")

    def get_column_name(self, obj):
        return self._lookup(
            UserScreenColumn, obj.column_id, "unique_id", "display_name"
        )

    def get_updated_by_name(self, obj):
        # updated_by is an Account id: a staff member's staff_unique_id, or a
        # platform/company User's unique_id. Rows from before the actor was
        # captured leave it blank.
        return (
            self._lookup(Staffcreation, obj.updated_by, "staff_unique_id", "employee_name")
            or self._lookup(User, obj.updated_by, "unique_id", "username")
            or obj.updated_by
        )
