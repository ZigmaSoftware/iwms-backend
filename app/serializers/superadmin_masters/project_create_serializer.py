from rest_framework import serializers

from app.models.superadmin_masters.project import Project

class ProjectCreateSerializer(serializers.Serializer):
    company_unique_id = serializers.CharField(max_length=30, required=False)
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    admin_username = serializers.CharField(max_length=150, required=False)
    admin_password = serializers.CharField(write_only=True, min_length=8, required=False)
    admin_employee_name = serializers.CharField(max_length=200, required=False)
    admin_email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)


class ProjectUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ProjectSerializer(serializers.ModelSerializer):
    company_unique_id = serializers.CharField(source="company_id.unique_id", read_only=True)

    class Meta:
        model = Project
        fields = ["unique_id", "company_unique_id", "name", "description", "is_active"]
        read_only_fields = ["unique_id", "company_unique_id", "is_active"]
