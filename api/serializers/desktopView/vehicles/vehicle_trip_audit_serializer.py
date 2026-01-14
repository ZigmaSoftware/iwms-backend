from rest_framework import serializers
from django.utils import timezone

from api.apps.vehicle_trip_audit import VehicleTripAudit
from api.apps.trip_instance import TripInstance
from api.apps.vehicleCreation import VehicleCreation


class VehicleTripAuditSerializer(serializers.ModelSerializer):

    trip_instance_id = serializers.SlugRelatedField(
        source="trip_instance",
        slug_field="unique_id",
        queryset=TripInstance.objects.all()
    )

    vehicle_id = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="unique_id",
        queryset=VehicleCreation.objects.all()
    )

    class Meta:
        model = VehicleTripAudit
        fields = [
            "id",
            "trip_instance_id",
            "vehicle_id",
            "gps_lat",
            "gps_lon",
            "avg_speed",
            "idle_seconds",
            "captured_at",
            "created_at",
        ]
        read_only_fields = ["id", "idle_seconds", "created_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        lat = attrs.get("gps_lat")
        lon = attrs.get("gps_lon")

        if lat is None and instance:
            lat = instance.gps_lat
        if lon is None and instance:
            lon = instance.gps_lon

        if not lat or not lon:
            raise serializers.ValidationError("GPS arrays cannot be empty")

        if len(lat) != len(lon):
            raise serializers.ValidationError("Latitude & Longitude array size mismatch")

        if len(lat) < 2:
            raise serializers.ValidationError("Minimum 2 GPS points required")

        try:
            [float(x) for x in lat]
            [float(x) for x in lon]
        except (TypeError, ValueError):
            raise serializers.ValidationError("GPS arrays must be numeric values")

        trip = attrs.get("trip_instance") or (instance.trip_instance if instance else None)
        if not trip:
            raise serializers.ValidationError("Trip instance is required")
        if trip.status != "IN_PROGRESS":
            raise serializers.ValidationError(
                "GPS audit allowed only for in-progress trips"
            )

        vehicle = attrs.get("vehicle") or (instance.vehicle if instance else None)
        if vehicle and vehicle != trip.vehicle:
            raise serializers.ValidationError("Vehicle does not match trip instance")

        return attrs

    def calculate_idle_time(self, speed, points_count):
        """
        Idle if speed <= 3 km/h.
        Each point = 5 seconds.
        """
        if speed <= 3:
            return points_count * 5
        return 0

    def create(self, validated_data):
        speed = validated_data["avg_speed"]
        points = len(validated_data["gps_lat"])

        validated_data["idle_seconds"] = self.calculate_idle_time(
            speed, points
        )

        return super().create(validated_data)
