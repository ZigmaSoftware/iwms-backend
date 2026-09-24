# app/api/serializers/zone_serializer.py

from rest_framework import serializers
from app.models.masters.zone import Zone
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator


class ZoneSerializer(TenancyReadSerializerMixin,serializers.ModelSerializer):

    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

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
    state_name = serializers.SerializerMethodField()
    state_unique_id = serializers.SerializerMethodField()
    country_unique_id = serializers.SerializerMethodField()
    continent_unique_id = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    continent_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    city_unique_id = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    district_unique_id = serializers.SerializerMethodField()

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

    def get_state_name(self, obj):
        state = obj.state
        return state.name if state else None

    def get_state_unique_id(self, obj):
        state = obj.state
        return state.unique_id if state else None

    def get_country_name(self, obj):
        state = obj.state
        country = state.country if state else None
        return country.name if country else None

    def get_country_unique_id(self, obj):
        state = obj.state
        country = state.country if state else None
        return country.unique_id if country else None

    def get_continent_name(self, obj):
        state = obj.state
        continent = state.continent if state else None
        return continent.name if continent else None

    def get_continent_unique_id(self, obj):
        state = obj.state
        continent = state.continent if state else None
        return continent.unique_id if continent else None

    def get_city_name(self, obj):
        city = obj.city
        return city.name if city else None

    def get_city_unique_id(self, obj):
        city = obj.city
        return city.unique_id if city else None

    def get_district_name(self, obj):
        district = obj.district
        return district.name if district else None

    def get_district_unique_id(self, obj):
        district = obj.district
        return district.unique_id if district else None

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
