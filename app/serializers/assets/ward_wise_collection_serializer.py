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

    ward_name             = serializers.CharField(source="ward_id.ward_name", read_only=True)
    zone_id               = serializers.CharField(source="ward_id.zone_id.unique_id", read_only=True)  # ✅ for zone_id
    zone_name             = serializers.CharField(source="ward_id.zone_id.zone_name", read_only=True)  # ✅ for zone_name
    wastetype_name        = serializers.CharField(source="waste_type_id.waste_type_name", read_only=True)
    bin_name              = serializers.CharField(source="point_collection_id.bin_id.bin_name", read_only=True)
    collection_point_name = serializers.CharField(source="point_collection_id.collection_point_id.cp_name", read_only=True)
    latitude              = serializers.SerializerMethodField()
    longitude             = serializers.SerializerMethodField()

    def get_latitude(self, obj):
        if obj.point_collection_id and obj.point_collection_id.collection_point_id:
            return obj.point_collection_id.collection_point_id.latitude
        return None

    def get_longitude(self, obj):
        if obj.point_collection_id and obj.point_collection_id.collection_point_id:
            return obj.point_collection_id.collection_point_id.longitude
        return None

    class Meta:
        model = WardCollection
        fields = [
            "unique_id",
            "ward_id",
            "ward_name",
            "zone_id",
            "zone_name",
            "waste_type_id",
            "wastetype_name",
            "ward_total_weight",
            "point_collection_id",
            "bin_name",
            "collection_point_name",
            "collection_date",
            "trip_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "latitude",
            "longitude",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]