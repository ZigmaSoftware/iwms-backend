from rest_framework import serializers


class PlatformCompanyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    admin_username = serializers.CharField(max_length=150)
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_employee_name = serializers.CharField(max_length=200)
    admin_email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
