from rest_framework import serializers

from api.apps.route_stop import RouteStop


class RouteStopSerializer(serializers.ModelSerializer):
    stop_type = serializers.CharField(read_only=True)
    property_name = serializers.CharField(
        source="property.property_name", read_only=True
    )
    sub_property_name = serializers.CharField(
        source="sub_property.sub_property_name", read_only=True
    )
    ward_name = serializers.CharField(source="ward.name", read_only=True)

    class Meta:
        model = RouteStop
        fields = [
            "id",
            "unique_id",
            "route_id",
            "ward",
            "ward_name",
            "zone",
            "cluster_id",
            "property",
            "property_name",
            "sub_property",
            "sub_property_name",
            "customer",
            "stop_type",
            "service_profile_id",
            "allowed_vehicle_classes",
            "waste_categories",
            "expected_load_weight_kg",
            "sequence_no",
            "is_mandatory",
            "expected_time",
            "service_window_start",
            "service_window_end",
            "estimated_duration_sec",
            "latitude",
            "longitude",
            "entrance_latitude",
            "entrance_longitude",
            "geofence",
            "access_notes",
            "hazard_flags",
            "contact_name",
            "contact_phone",
            "status",
            "actual_arrival_at",
            "actual_departure_at",
            "notes",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "unique_id",
            "stop_type",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    def _derive_stop_type(self, attrs):
        sub_property = attrs.get("sub_property") or getattr(
            getattr(self, "instance", None), "sub_property", None
        )
        if sub_property:
            maybe = (sub_property.sub_property_name or "").lower()
            if maybe in dict(RouteStop.StopType.choices):
                return maybe

        prop = attrs.get("property") or getattr(
            getattr(self, "instance", None), "property", None
        )
        if prop:
            maybe = (prop.property_name or "").lower()
            if maybe in dict(RouteStop.StopType.choices):
                return maybe
        return RouteStop.StopType.HOUSE

    def create(self, validated_data):
        validated_data["stop_type"] = self._derive_stop_type(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data["stop_type"] = self._derive_stop_type(validated_data)
        return super().update(instance, validated_data)
