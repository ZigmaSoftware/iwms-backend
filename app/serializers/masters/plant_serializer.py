from rest_framework import serializers

from app.models.masters.plant import Plant
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class PlantSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Plant
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "name",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]

    def validate_project_id(self, project):
        existing = Plant.objects.filter(project_id=project, is_deleted=False)
        if self.instance:
            existing = existing.exclude(unique_id=self.instance.unique_id)
        if existing.exists():
            raise serializers.ValidationError("This project already has a plant.")
        return project
