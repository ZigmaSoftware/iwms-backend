from rest_framework import serializers
from app.models.masters.ward import Ward
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.validators.unique_name_validator import unique_name_validator


class WardSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    hierarchy_name = serializers.CharField(source="hierarchy_id.level_name", read_only=True)
    zone_name = serializers.CharField(source="zone_id.zone_name", read_only=True)
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True)

    continent_name = serializers.CharField(source="state_id.continent_id.name", read_only=True)
    country_name = serializers.CharField(source="state_id.country_id.name", read_only=True)
    continent_id = serializers.CharField(source="state_id.continent_id.unique_id", read_only=True)
    country_id = serializers.CharField(source="state_id.country_id.unique_id", read_only=True)

    hierarchy_order = serializers.IntegerField(
        source="hierarchy_id.hierarchy_order",
        read_only=True
    )

    class Meta:
        model = Ward
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            "continent_id",
            "continent_name",
            "country_id",
            "country_name",

            "state_id",
            "state_name",
            "city_id",
            "city_name",
            "district_id",
            "district_name",

            "zone_id",
            "zone_name",
            "panchayat_id",
            "panchayat_name",

            "hierarchy_id",
            "hierarchy_order",
            "hierarchy_name",

            "ward_name",
            "description",

            "geofencing_type",

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

        hierarchy = attrs.get("hierarchy_id") or getattr(self.instance, "hierarchy_id", None)
        ward_name = attrs.get("ward_name")

        zone = attrs.get("zone_id") if "zone_id" in attrs else getattr(self.instance, "zone_id", None)
        panchayat = attrs.get("panchayat_id") if "panchayat_id" in attrs else getattr(self.instance, "panchayat_id", None)

        if zone and panchayat:
            raise serializers.ValidationError(
                "Ward can belong to either Zone or Panchayat."
            )

        if not zone and not panchayat:
            raise serializers.ValidationError(
                "Ward must belong to Zone or Panchayat."
            )

        if hierarchy and hierarchy.level_name.lower() != "ward":
            raise serializers.ValidationError({
                "hierarchy": "Hierarchy level must be ward."
            })

        if not self.instance or ward_name:
            unique_name_validator(
                Model=Ward,
                name_field="ward_name",
                scope_fields=[
                    "company_id",
                    "project_id",
                    "city_id",
                    "district_id",
                    "state_id"
                ]
            )(self, attrs)

        return attrs
