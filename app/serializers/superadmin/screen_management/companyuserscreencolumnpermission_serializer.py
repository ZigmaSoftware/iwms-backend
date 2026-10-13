from rest_framework import serializers

from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn


class CompanyUserScreenColumnPermissionSerializer(serializers.ModelSerializer):
    column_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    data_type = serializers.SerializerMethodField()
    userscreen_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = CompanyUserScreenColumnPermission
        fields = "__all__"

    def _column(self, obj):
        return UserScreenColumn.objects.filter(unique_id=obj.column_id).first()

    def get_column_name(self, obj):
        col = self._column(obj)
        return col.field_name if col else ""

    def get_display_name(self, obj):
        col = self._column(obj)
        return col.display_name if col else ""

    def get_data_type(self, obj):
        col = self._column(obj)
        return col.data_type if col else ""

    def get_userscreen_name(self, obj):
        screen = UserScreen.objects.filter(unique_id=obj.userscreen_id).first()
        return screen.userscreen_name if screen else ""

    def get_company_name(self, obj):
        from app.models.superadmin_masters.company import Company
        company = Company.objects.filter(unique_id=obj.company_id).first()
        return company.name if company else ""

    def get_project_name(self, obj):
        from app.models.superadmin_masters.project import Project
        project = Project.objects.filter(unique_id=obj.project_id).first()
        return project.name if project else ""


# ---------------------------------------------------------------------------
# Dedicated column-permission API serializers
# ---------------------------------------------------------------------------

class UserScreenColumnPermissionSerializer(serializers.ModelSerializer):
    """
    Read serializer returning the frontend-facing clean format.
    Maps: unique_id → userscreencolumnpermission_id
          column_id  → userscreencolumn_id
          can_view   → is_active
    """

    userscreencolumnpermission_id = serializers.CharField(source="unique_id", read_only=True)
    userscreencolumn_id = serializers.CharField(source="column_id", read_only=True)
    column_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source="can_view", read_only=True)
    userscreen_name = serializers.SerializerMethodField()

    def get_column_name(self, obj):
        col = UserScreenColumn.objects.filter(unique_id=obj.column_id).first()
        return (col.display_name or col.field_name) if col else ""

    def get_userscreen_name(self, obj):
        screen = UserScreen.objects.filter(unique_id=obj.userscreen_id).first()
        return screen.userscreen_name if screen else ""

    class Meta:
        model = CompanyUserScreenColumnPermission
        fields = [
            "userscreen_name",
            "userscreencolumnpermission_id",
            "userscreencolumn_id",
            "column_name",
            "is_active",
        ]


class UserScreenColumnPermissionWriteSerializer(serializers.Serializer):
    """
    Write serializer for create operations.
    Validates that column_id belongs to the given userscreen_id.
    """

    userscreen_id = serializers.CharField()
    column_id = serializers.CharField()
    project_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    projectId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    is_active = serializers.BooleanField(default=True)
    order_no = serializers.IntegerField(default=1, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_userscreen_id(self, value):
        if not UserScreen.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError("Invalid userscreen_id.")
        return value

    def validate_column_id(self, value):
        if not UserScreenColumn.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError("Invalid column_id.")
        return value

    def validate(self, data):
        data["project_id"] = (
            data.get("project_id")
            or data.get("projectId")
            or ""
        ).strip() or None
        userscreen_id = data.get("userscreen_id")
        column_id = data.get("column_id")
        if userscreen_id and column_id:
            if not UserScreenColumn.objects.filter(
                unique_id=column_id,
                userscreen_id=userscreen_id,
                is_deleted=False,
            ).exists():
                raise serializers.ValidationError(
                    {"column_id": "Column does not belong to the specified userscreen."}
                )
        return data
