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

    # `coordinates` is the single read/write field for the ward boundary —
    # the dashboard map layers (useWardGeofences/WardGeofenceLayer/
    # WardMapPanel) already read `coordinates` on every ward list response.
    # `boundary_coordinates` (the underlying model field) stays read-only
    # here so there is exactly one writable path onto it.
    coordinates = serializers.JSONField(source="boundary_coordinates", required=False, allow_null=True)
    local_body_type = serializers.SerializerMethodField()
    local_body_name = serializers.SerializerMethodField()

    def get_local_body_type(self, obj):
        if obj.zone_id_id:
            return "Zone"
        if obj.panchayat_id_id:
            return "Panchayat"
        return None

    def get_local_body_name(self, obj):
        if obj.zone_id_id:
            return obj.zone_id.zone_name
        if obj.panchayat_id_id:
            return obj.panchayat_id.panchayat_name
        return None

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

            "hierarchy_id",
            "hierarchy_order",
            "hierarchy_name",

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
