from rest_framework import serializers
from django.utils import timezone
from api.apps.trip_attendance import TripAttendance
from api.apps.trip_instance import TripInstance
from api.apps.userCreation import User
from api.apps.vehicleCreation import VehicleCreation


class TripAttendanceSerializer(serializers.ModelSerializer):

    trip_instance_id = serializers.SlugRelatedField(
        source="trip_instance",
        slug_field="unique_id",
        queryset=TripInstance.objects.all()
    )

    staff_id = serializers.SlugRelatedField(
        source="staff",
        slug_field="unique_id",
        queryset=User.objects.all()
    )

    vehicle_id = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="unique_id",
        queryset=VehicleCreation.objects.all()
    )

    class Meta:
        model = TripAttendance
        fields = [
            "unique_id",
            "trip_instance_id",
            "staff_id",
            "vehicle_id",
            "attendance_time",
            "latitude",
            "longitude",
            "photo",
            "source",
            "created_at",
        ]
        read_only_fields = ["unique_id", "created_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        trip = attrs.get("trip_instance") if "trip_instance" in attrs else getattr(instance, "trip_instance", None)
        staff = attrs.get("staff") if "staff" in attrs else getattr(instance, "staff", None)
        vehicle = attrs.get("vehicle") if "vehicle" in attrs else getattr(instance, "vehicle", None)

        if instance:
            return attrs

        if not trip or not staff:
            return attrs

        # Trip must be active (create only)
        if trip.status != "IN_PROGRESS":
            raise serializers.ValidationError(
                "Attendance allowed only for in-progress trips"
            )

        if not trip.staff_template:
            raise serializers.ValidationError(
                "Trip has no staff template assigned"
            )

        # Staff must belong to trip
        if staff.unique_id not in [
            trip.staff_template.operator_id_id,
            trip.staff_template.driver_id_id,
        ]:
            raise serializers.ValidationError(
                "Staff is not assigned to this trip"
            )

        if staff.staffusertype_id and staff.staffusertype_id.name.lower() not in [
            "operator",
            "driver",
        ]:
            raise serializers.ValidationError(
                "Attendance allowed only for operator or driver"
            )

        if vehicle != trip.vehicle:
            raise serializers.ValidationError(
                "Vehicle does not match trip instance"
            )

        # 45-minute rule enforcement (create only)
        last = (
            TripAttendance.objects
            .filter(trip_instance=trip, staff=staff)
            .order_by("-attendance_time")
            .first()
        )

        if last:
            delta = timezone.now() - last.attendance_time
            if delta.total_seconds() < 45 * 60:
                raise serializers.ValidationError(
                    "Attendance already captured within last 45 minutes"
                )

        return attrs
