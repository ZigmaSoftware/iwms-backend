# from app.models.assets.panchayat_wise_collection import PanchayatCollection
# from rest_framework import serializers
# from app.models.assets.point_collection import PointCollection
# from app.models.user_creations.waste_collection_bluetooth import WasteType
# from app.models.assets.collection_point import Collection_point
# from app.models.transport_masters.trip import Trip
# from app.models.user_creations.stafftemplate import StaffTemplate
# from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


# class PanchayatCollectionSerializer(TenancyReadSerializerMixin,serializers.ModelSerializer):

#     panchayat_id = serializers.SlugRelatedField(
#         slug_field="unique_id",
#         read_only=True
#     )

#     waste_type_id = serializers.SlugRelatedField(
#         slug_field="unique_id",
#         read_only=True
#     )

#     trip_id = serializers.SlugRelatedField(
#         slug_field="unique_id",
#         read_only=True
#     )

#     panchayat_name = serializers.CharField(source = "panchayat_id.panchayat_name", read_only = True)
#     wastetype_name = serializers.CharField(source = "waste_type_id.waste_type_name", read_only = True)
#     point_collection_name = serializers.CharField(source = "point_collection_id.collection_point_id.cp_name", read_only = True)
#     latitude = serializers.SerializerMethodField()
#     longitude = serializers.SerializerMethodField()

#     def get_latitude(self, obj):
#         if obj.point_collection_id and obj.point_collection_id.collection_point_id:
#             return obj.point_collection_id.collection_point_id.latitude
#         return None

#     def get_longitude(self, obj):
#         if obj.point_collection_id and obj.point_collection_id.collection_point_id:
#             return obj.point_collection_id.collection_point_id.longitude
#         return None
    

#     class Meta:
#         model = PanchayatCollection
#         fields = [
#             "unique_id",
#             "panchayat_id",
#             "panchayat_name",
#             "waste_type_id",
#             "wastetype_name",
#             "panchayat_total_weight",
#             "point_collection_id",
#             "point_collection_name",
#             "collection_date",
#             "trip_id",
#             "company_id",
#             "company_name",
#             "project_id",
#             "project_name",
#             "latitude",
#             "longitude",
#             "is_active",
#             "is_deleted",
#             "created_at",
#             "updated_at",
#             "created_by",
#             "updated_by",
#         ]

#         read_only_fields = ["unique_id", "created_at", "updated_at"]




from app.models.assets.panchayat_wise_collection import PanchayatCollection
from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class PanchayatCollectionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    panchayat_id = serializers.SlugRelatedField(
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

    panchayat_name       = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True)
    wastetype_name       = serializers.CharField(source="waste_type_id.waste_type_name", read_only=True)
    bin_name             = serializers.CharField(source="point_collection_id.bin_id.bin_name", read_only=True)
    collection_point_name = serializers.CharField(source="point_collection_id.collection_point_id.cp_name", read_only=True)
    latitude             = serializers.SerializerMethodField()
    longitude            = serializers.SerializerMethodField()

    def get_latitude(self, obj):
        if obj.point_collection_id and obj.point_collection_id.collection_point_id:
            return obj.point_collection_id.collection_point_id.latitude
        return None

    def get_longitude(self, obj):
        if obj.point_collection_id and obj.point_collection_id.collection_point_id:
            return obj.point_collection_id.collection_point_id.longitude
        return None

    class Meta:
        model = PanchayatCollection
        fields = [
            "unique_id",
            "panchayat_id",
            "panchayat_name",
            "waste_type_id",
            "wastetype_name",
            "panchayat_total_weight",
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