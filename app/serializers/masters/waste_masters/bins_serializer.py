from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.models.assets.bins import Bins
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.validators.unique_name_validator import unique_name_validator

class BinsSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    district_name = serializers.CharField(source="district_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    wastetype_name = serializers.CharField(source="wastetype_id.waste_type_name", read_only=True)
    collection_point_name = serializers.CharField(source="collection_point_id.cp_name", read_only=True)

    panchayat_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Panchayat.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True)

    zone_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Zone.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    zone_name = serializers.CharField(source="zone_id.zone_name", read_only=True)

    ward_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
    )
    ward_name = serializers.CharField(source="ward_id.ward_name", read_only=True)

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
        collection_point = attrs.get(
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

        if ward and collection_point and not collection_point.wards.filter(
            unique_id=ward.unique_id
        ).exists():
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
