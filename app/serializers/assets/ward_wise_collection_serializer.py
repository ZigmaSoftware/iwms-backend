from rest_framework import serializers
from app.models.assets.ward_wise_collection import WardCollection
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class WardCollectionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    ward_id = serializers.SlugRelatedField(
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

    ward_name = serializers.CharField(source="ward_id.ward_name", read_only=True)
    wastetype_name = serializers.CharField(source="waste_type_id.waste_type_name", read_only=True)

    class Meta:
        model = WardCollection
        fields = [
            "unique_id",
            "ward_id",
            "ward_name",
            "waste_type_id",
            "wastetype_name",
            "ward_total_weight",
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