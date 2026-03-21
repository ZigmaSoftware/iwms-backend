from rest_framework import serializers
from app.models.collections.zone_wise_collection import ZoneCollection
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class ZoneCollectionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    zone_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        read_only=True
    )

    waste_type_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        read_only=True
    )

    trip_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        read_only=True
    )

    zone_name      = serializers.CharField(source="zone_id.zone_name",           read_only=True)
    wastetype_name = serializers.CharField(source="waste_type_id.waste_type_name", read_only=True)

    class Meta:
        model = ZoneCollection
        fields = [
            "unique_id",
            "zone_id",
            "zone_name",
            "waste_type_id",
            "wastetype_name",
            "zone_total_weight",
            "ward_count",
            "collection_date",
            "trip_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id", "zone_total_weight", "ward_count", "created_at", "updated_at"]