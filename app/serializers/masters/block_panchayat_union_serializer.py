from rest_framework import serializers
from app.models.masters.block_panchayat_union import BlockPanchayatUnion
from app.models.masters.district import District
from app.models.common_masters.state import State
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator


class BlockPanchayatUnionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    state_id = NameOrUniqueIdField(
        queryset=State.objects.filter(is_deleted=False),
        name_field="name",
    )
    district_id = NameOrUniqueIdField(
        queryset=District.objects.filter(is_deleted=False),
        name_field="name",
        scope_fields=["state_id"],
    )

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)

    class Meta:
        model = BlockPanchayatUnion
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "block_name",
            "description",
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
            "company_id",
            "project_id",
        ]

    def validate(self, attrs):
        block_name = attrs.get("block_name")

        if not self.instance or block_name:
            unique_name_validator(
                Model=BlockPanchayatUnion,
                name_field="block_name",
                scope_fields=["company_id", "project_id", "district_id", "state_id"],
            )(self, attrs)

        return attrs
