from rest_framework import serializers
from app.models.masters.ward import Ward
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.superadmin.common_masters.state import State
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator


class WardSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

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
    zone_id = NameOrUniqueIdField(
        queryset=Zone.objects.filter(is_deleted=False),
        name_field="zone_name",
        scope_fields=["city_id", "district_id", "state_id"],
        required=False,
        allow_null=True,
    )
    panchayat_id = NameOrUniqueIdField(
        queryset=Panchayat.objects.filter(is_deleted=False),
        name_field="panchayat_name",
        scope_fields=["city_id", "district_id", "state_id"],
        required=False,
        allow_null=True,
    )

    state_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    panchayat_name = serializers.SerializerMethodField()

    continent_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    continent_id = serializers.SerializerMethodField()
    country_id = serializers.SerializerMethodField()

    # `coordinates` is the single read/write field for the ward boundary —
    # the dashboard map layers (useWardGeofences/WardGeofenceLayer/
    # WardMapPanel) already read `coordinates` on every ward list response.
    # `boundary_coordinates` (the underlying model field) stays read-only
    # here so there is exactly one writable path onto it.
    coordinates = serializers.JSONField(source="boundary_coordinates", required=False, allow_null=True)
    local_body_type = serializers.SerializerMethodField()
    local_body_name = serializers.SerializerMethodField()

    def get_local_body_type(self, obj):
        if obj.zone_id:
            return "Zone"
        if obj.panchayat_id:
            return "Panchayat"
        return None

    def get_local_body_name(self, obj):
        if obj.zone_id:
            zone = Zone.objects.filter(unique_id=obj.zone_id).first()
            return zone.zone_name if zone else None
        if obj.panchayat_id:
            panchayat = Panchayat.objects.filter(unique_id=obj.panchayat_id).first()
            return panchayat.panchayat_name if panchayat else None
        return None

    def get_state_name(self, obj):
        state = State.objects.filter(unique_id=obj.state_id).first()
        return state.name if state else None

    def get_city_name(self, obj):
        city = City.objects.filter(unique_id=obj.city_id).first()
        return city.name if city else None

    def get_district_name(self, obj):
        district = District.objects.filter(unique_id=obj.district_id).first()
        return district.name if district else None

    def get_zone_name(self, obj):
        zone = Zone.objects.filter(unique_id=obj.zone_id).first()
        return zone.zone_name if zone else None

    def get_panchayat_name(self, obj):
        panchayat = Panchayat.objects.filter(unique_id=obj.panchayat_id).first()
        return panchayat.panchayat_name if panchayat else None

    def _state(self, obj):
        return State.objects.filter(unique_id=obj.state_id).first()

    def get_continent_name(self, obj):
        state = self._state(obj)
        if not state or not state.continent_id:
            return None
        from app.models.superadmin.common_masters.continent import Continent
        continent = Continent.objects.filter(unique_id=state.continent_id).first()
        return continent.name if continent else None

    def get_country_name(self, obj):
        state = self._state(obj)
        if not state or not state.country_id:
            return None
        from app.models.superadmin.common_masters.country import Country
        country = Country.objects.filter(unique_id=state.country_id).first()
        return country.name if country else None

    def get_continent_id(self, obj):
        state = self._state(obj)
        return state.continent_id if state else None

    def get_country_id(self, obj):
        state = self._state(obj)
        return state.country_id if state else None

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
            "local_body_type",
            "local_body_name",

            "ward_name",
            "description",

            "latitude",
            "longitude",
            "geofencing_type",
            "boundary_coordinates",
            "coordinates",

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
            "boundary_coordinates",
        ]

    def validate(self, attrs):

        coordinates = attrs.get("boundary_coordinates")
        if coordinates is not None:
            if not isinstance(coordinates, list):
                raise serializers.ValidationError(
                    {"coordinates": "Must be a list of {latitude, longitude} points."}
                )
            for point in coordinates:
                if not isinstance(point, dict) or "latitude" not in point or "longitude" not in point:
                    raise serializers.ValidationError(
                        {"coordinates": "Each point needs a latitude and longitude."}
                    )
                try:
                    lat = float(point["latitude"])
                    lng = float(point["longitude"])
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        {"coordinates": "latitude/longitude must be numbers."}
                    )
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    raise serializers.ValidationError(
                        {"coordinates": "latitude/longitude out of range."}
                    )
            if coordinates and len(coordinates) < 3:
                raise serializers.ValidationError(
                    {"coordinates": "A boundary needs at least 3 points to form a polygon."}
                )

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
