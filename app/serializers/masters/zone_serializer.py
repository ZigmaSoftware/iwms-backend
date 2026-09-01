# app/api/serializers/zone_serializer.py

from rest_framework import serializers
from app.models.masters.zone import Zone
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.validators.unique_name_validator import unique_name_validator


class ZoneSerializer(TenancyReadSerializerMixin,serializers.ModelSerializer):

    state_name        = serializers.CharField(source="state_id.name", read_only=True)
    state_unique_id   = serializers.CharField(source="state_id.unique_id", read_only=True)
    country_unique_id = serializers.CharField(source="state_id.country_id.unique_id", read_only=True)
    continent_unique_id = serializers.CharField(source="state_id.continent_id.unique_id", read_only=True)
    country_name      = serializers.CharField(source="state_id.country_id.name", read_only=True)
    continent_name    = serializers.CharField(source="state_id.continent_id.name", read_only=True)
    city_name         = serializers.CharField(source="city_id.name", read_only=True)
    city_unique_id    = serializers.CharField(source="city_id.unique_id", read_only=True)
    district_name     = serializers.CharField(source="district_id.name", read_only=True)
    district_unique_id = serializers.CharField(source="district_id.unique_id", read_only=True)

    class Meta:
        model = Zone
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            "country_unique_id",
            "country_name",
            "continent_unique_id",
            "continent_name",

            "state_id",
            "state_unique_id",
            "state_name",
            "city_id",
            "city_unique_id",
            "city_name",
            "district_id",
            "district_unique_id",
            "district_name",

            "zone_name",
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

        # -------------------------------
        # GET VALUES (Handle Update Case)
        # -------------------------------
        zone_name = attrs.get("zone_name")

        # -------------------------------
        # Unique Zone Name
        # -------------------------------
        if not self.instance or zone_name:
            unique_name_validator(
                Model=Zone,
                name_field="zone_name",
                scope_fields=[
                    "company_id",
                    "project_id",
                    "city_id",
                    "district_id",
                    "state_id"
                ]
            )(self, attrs)

        return attrs
