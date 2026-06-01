from rest_framework import serializers
from app.models.collections.ward_wise_collection import WardCollection
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
    bin_name              = serializers.SerializerMethodField()
    collection_point_name = serializers.SerializerMethodField()
    latitude              = serializers.SerializerMethodField()
    longitude             = serializers.SerializerMethodField()

    def _collection_point(self, obj):
        if obj.bin_collection_event_id:
            return obj.bin_collection_event_id.collection_point_id
        if obj.point_collection_id:
            return obj.point_collection_id.collection_point_id
        return None

    def _bin(self, obj):
        if obj.bin_collection_event_id:
            return obj.bin_collection_event_id.bin_id
        if obj.point_collection_id:
            return obj.point_collection_id.bin_id
        return None

    def get_bin_name(self, obj):
        bin_obj = self._bin(obj)
        return getattr(bin_obj, "bin_name", None)

    def get_collection_point_name(self, obj):
        collection_point = self._collection_point(obj)
        return getattr(collection_point, "cp_name", None)

    def get_latitude(self, obj):
        collection_point = self._collection_point(obj)
        return getattr(collection_point, "latitude", None)

    def get_longitude(self, obj):
        collection_point = self._collection_point(obj)
        return getattr(collection_point, "longitude", None)

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
            "bin_collection_event_id",
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
