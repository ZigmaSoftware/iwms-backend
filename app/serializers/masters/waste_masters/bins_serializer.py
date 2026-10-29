from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.models.masters.waste_masters.bins import Bins
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.related_prefetch import prefetching_list_serializer, related
from app.validators.unique_name_validator import unique_name_validator

RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "district": (District, "district_id"),
    "city": (City, "city_id"),
    "wastetype": (WasteType, "wastetype_id"),
    "collection_point": (Collection_point, "collection_point_id"),
    "panchayat": (Panchayat, "panchayat_id"),
    "zone": (Zone, "zone_id"),
    "ward": (Ward, "ward_id"),
}

class BinsSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    district_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    wastetype_name = serializers.SerializerMethodField()
    collection_point_name = serializers.SerializerMethodField()

    panchayat_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Panchayat.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    panchayat_name = serializers.SerializerMethodField()

    zone_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Zone.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    zone_name = serializers.SerializerMethodField()

    ward_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    ward_name = serializers.SerializerMethodField()

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
            "latitude",
            "longitude",
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
            "latitude": {"required": False, "allow_null": True},
            "longitude": {"required": False, "allow_null": True},
        }
        list_serializer_class = prefetching_list_serializer(RELATED_LOOKUPS)

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def get_district_name(self, obj):
        district = related(obj, "district", District, "district_id")
        return district.name if district else None

    def get_city_name(self, obj):
        city = related(obj, "city", City, "city_id")
        return city.name if city else None

    def get_wastetype_name(self, obj):
        waste_type = related(obj, "wastetype", WasteType, "wastetype_id")
        return waste_type.waste_type_name if waste_type else None

    def get_collection_point_name(self, obj):
        cp = related(obj, "collection_point", Collection_point, "collection_point_id")
        return cp.cp_name if cp else None

    def get_panchayat_name(self, obj):
        panchayat = related(obj, "panchayat", Panchayat, "panchayat_id")
        return panchayat.panchayat_name if panchayat else None

    def get_zone_name(self, obj):
        zone = related(obj, "zone", Zone, "zone_id")
        return zone.zone_name if zone else None

    def get_ward_name(self, obj):
        ward = related(obj, "ward", Ward, "ward_id")
        return ward.ward_name if ward else None


    def validate(self, attrs):
        collection_point_id = attrs.get(
            "collection_point_id",
            getattr(self.instance, "collection_point_id", None),
        )
        ward = attrs.get("ward_id", getattr(self.instance, "ward_id", None))
        zone = attrs.get("zone_id", getattr(self.instance, "zone_id", None))
        panchayat = attrs.get("panchayat_id", getattr(self.instance, "panchayat_id", None))

        if zone and panchayat:
            raise serializers.ValidationError(
                {"zone_id": "A bin cannot belong to both a Zone and a Panchayat."}
            )

        if ward and collection_point_id:
            collection_point = Collection_point.objects.filter(unique_id=collection_point_id).first()
            ward_uid = ward.unique_id if hasattr(ward, "unique_id") else ward
            if collection_point and ward_uid not in collection_point.get_ward_ids():
                raise serializers.ValidationError(
                    {"ward_id": "Selected ward is not one of the selected collection point's wards."}
                )

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
