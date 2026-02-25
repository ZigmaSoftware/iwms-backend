from rest_framework import serializers
from app.models.assets.point_collection import PointCollection
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.assets.collection_point import Collection_point
from app.models.transport_masters.trip import Trip
from app.models.user_creations.stafftemplate import StaffTemplate
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class PointCollectionSerializer(TenancyReadSerializerMixin,serializers.ModelSerializer):

    waste_type_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=WasteType.objects.all()
    )

    collection_point_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Collection_point.objects.all()
    )


    trip_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Trip.objects.all()
    )


    bin_name = serializers.CharField(source = "bin_id.bin_name", read_only = True)
    collection_point_name = serializers.CharField(source = "collection_point_id.cp_name", read_only = True)
    wastetype_name = serializers.CharField(source = "waste_type_id.waste_type_name", read_only = True)
    panchayat_id = serializers.CharField(source = "collection_point_id.panchayat_id", read_only = True)
    panchayat_name = serializers.CharField(source = "collection_point_id.panchayat_id.panchayat_name", read_only = True)
    ward_id = serializers.CharField(source = "collection_point_id.ward_id", read_only = True)
    ward_name = serializers.CharField(source = "collection_point_id.ward_id.ward_name", read_only = True)

    class Meta:
        model = PointCollection
        fields = [
            "unique_id",
            "bin_id",
            "bin_name",
            "waste_type_id",
            "wastetype_name",
            "collection_point_id",
            "collection_point_name",
            "point_collection_weight",
            "collection_date",
            "collection_time",
            "trip_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "panchayat_id",
            "panchayat_name",
            "ward_id",
            "ward_name",
            "is_collected",
            "created_by",
            "updated_by",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]