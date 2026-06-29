from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.assets.bins import Bins
from app.validators.unique_name_validator import unique_name_validator

class BinsSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    panchayat_name = serializers.CharField(source="collection_point_id.panchayat_id.panchayat_name", read_only=True)
    panchayat_id = serializers.CharField(source="collection_point_id.panchayat_id.unique_id", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    wastetype_name = serializers.CharField(source="wastetype_id.waste_type_name", read_only=True)
    collection_point_name = serializers.CharField(source="collection_point_id.cp_name", read_only=True)

    # Derived from the first ward in the wards M2M on the collection point
    ward_id = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    zone_id = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()

    def get_ward_id(self, obj):
        w = obj.collection_point_id.wards.first()
        return w.unique_id if w else None

    def get_ward_name(self, obj):
        w = obj.collection_point_id.wards.first()
        return w.ward_name if w else None

    def get_zone_id(self, obj):
        w = obj.collection_point_id.wards.select_related("zone_id").first()
        return w.zone_id.unique_id if w and w.zone_id else None

    def get_zone_name(self, obj):
        w = obj.collection_point_id.wards.select_related("zone_id").first()
        return w.zone_id.zone_name if w and w.zone_id else None

    class Meta:
        model = Bins
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "panchayat_id",
            "panchayat_name",
            "district_id",
            "district_name",
            "city_id",
            "city_name",
            "zone_id",
            "zone_name",
            "ward_id",
            "ward_name",
            "collection_point_id",
            "collection_point_name",
            "bin_capacity",
            "bin_name",
            "bin_type",
            "bin_image",
            "bin_qr",
            "wastetype_id",
            "wastetype_name",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_active",
            "is_deleted"
        ]
        read_only_fields = [
            "unique_id",
            "bin_qr",
            "created_at",
            "updated_at",
            "is_deleted"
        ]
        extra_kwargs = {
            "bin_qr": {"required": False, "read_only": True},
            "bin_image": {"required": False, "allow_blank": True},
        }


    def validate(self, attrs):
        if attrs.get("bin_qr") is None:
            attrs["bin_qr"] = ""

        if not attrs.get("bin_image"):
            attrs["bin_image"] = "default.png"
        
        if self.instance and "bin_name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=Bins,
            name_field="bin_name", 
            scope_fields=["company_id","project_id","wastetype_id","collection_point_id"]  
        )(self, attrs)
