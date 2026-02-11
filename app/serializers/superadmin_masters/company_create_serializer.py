from rest_framework import serializers

from app.models.superadmin_masters.company import Company

class PlatformCompanyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["unique_id", "name", "description", "is_active"]
        read_only_fields = ["unique_id", "is_active"]
