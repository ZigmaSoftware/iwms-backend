from rest_framework import serializers

from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)


class CompanyUserScreenColumnPermissionSerializer(serializers.ModelSerializer):
    column_name = serializers.CharField(source="column_id.field_name", read_only=True)
    display_name = serializers.CharField(source="column_id.display_name", read_only=True)
    data_type = serializers.CharField(source="column_id.data_type", read_only=True)
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    company_name = serializers.CharField(source="company_id.name", read_only=True)
    project_name = serializers.CharField(source="project_id.name", read_only=True)

    class Meta:
        model = CompanyUserScreenColumnPermission
        fields = "__all__"
