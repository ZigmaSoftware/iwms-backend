from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.masters.panchayat import Panchayat
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.block_panchayat_union import BlockPanchayatUnion
from app.models.common_masters.state import State
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator


class PanchayatSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    state_id = NameOrUniqueIdField(
        queryset=State.objects.filter(is_deleted=False),
        name_field="name",
    )
    district_id = NameOrUniqueIdField(
        queryset=District.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["state_id"],
    )
    city_id = NameOrUniqueIdField(
        queryset=City.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["district_id", "state_id"],
    )
    block_id = NameOrUniqueIdField(
        queryset=BlockPanchayatUnion.objects.filter(is_deleted=False),
        name_field="block_name",
        scope_fields=["district_id", "state_id"],
        required=False,
        allow_null=True,
    )

    state_name        = serializers.CharField(source="state_id.name", read_only=True)
    state_unique_id   = serializers.CharField(source="state_id.unique_id", read_only=True)
    city_name         = serializers.CharField(source="city_id.name", read_only=True)
    city_unique_id    = serializers.CharField(source="city_id.unique_id", read_only=True)
    district_name     = serializers.CharField(source="district_id.name", read_only=True)
    district_unique_id = serializers.CharField(source="district_id.unique_id", read_only=True)
    block_name = serializers.CharField(source="block_id.block_name", read_only=True)

    class Meta:
        model = Panchayat
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "state_id",
            "state_unique_id",
            "state_name",
            "city_id",
            "city_unique_id",
            "city_name",
            "district_id",
            "district_unique_id",
            "district_name",
            "block_id",
            "block_name",
            "panchayat_name",
            "agreed_weight_kg",
            "weight_unit",
            "effective_from",
            "geofencing_type",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]


    def validate(self, attrs):

        # -------------------------------
        # GET VALUES (Handle Update Case)
        # -------------------------------
        panchayat_name = attrs.get("panchayat_name")

        # -------------------------------
        # Unique Panchayat Name
        # -------------------------------
        if not self.instance or panchayat_name:
            unique_name_validator(
                Model=Panchayat,
                name_field="panchayat_name",
                scope_fields=[
                    "company_id",
                    "project_id",
                    "city_id",
                    "district_id",
                    "state_id"
                ]
            )(self, attrs)

        return attrs
