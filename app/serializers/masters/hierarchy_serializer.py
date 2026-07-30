# app/api/serializers/hierarchy_serializer.py

from rest_framework import serializers
from app.models.masters.hierarchy import AdministrativeHierarchy


class AdministrativeHierarchySerializer(serializers.ModelSerializer):
    class Meta:

        model = AdministrativeHierarchy
        fields = [
            "unique_id",
            "level_name",
            "is_active",
        ]
        read_only_fields = ("unique_id",)
