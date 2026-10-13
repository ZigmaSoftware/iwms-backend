from rest_framework import serializers

from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField


class TripDelayReportSerializer(serializers.ModelSerializer):
    """Read/write for the delay log.

    The driver supplies only `trip_assignment_id`, `delay_reason` and
    `delay_remarks` (plus optional minutes/location). Everything else —
    tenant scope, reporter, timestamps, status — is stamped server-side, so a
    client cannot report a delay against another crew's trip or backdate one.
    """

    trip_assignment_id = UniqueIdOrPkField(
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )

    # Flattened read-only context so the supervisor list needs no extra calls.
    delay_reason_display = serializers.CharField(
        source="get_delay_reason_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    reported_by = serializers.CharField(source="reported_by_id", read_only=True)
    acknowledged_by = serializers.CharField(
        source="acknowledged_by_id", read_only=True, default=None
    )
    # reported_by_id / vehicle_id are plain id strings, so resolve the names
    # explicitly rather than via a dotted `source` (which would silently hit
    # the default every time).
    reported_by_name = serializers.SerializerMethodField()
    vehicle_no = serializers.CharField(
        source="trip_assignment.vehicle.vehicle_no",
        read_only=True,
        default=None,
    )
    trip_date = serializers.DateField(
        source="trip_assignment.trip_date", read_only=True, default=None
    )

    class Meta:
        model = TripDelayReport
        fields = [
            "unique_id",
            "company_id",
            "project_id",
            "trip_assignment_id",
            "trip_date",
            "vehicle_no",
            "reported_by",
            "reported_by_name",
            "delay_reason",
            "delay_reason_display",
            "delay_remarks",
            "estimated_delay_minutes",
            "delay_time",
            "delay_lat",
            "delay_lng",
            "delay_location",
            "status",
            "status_display",
            "acknowledged_by",
            "acknowledged_at",
            "supervisor_remarks",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            # Server-stamped: see the class docstring.
            "company_id",
            "project_id",
            "reported_by",
            "delay_time",
            "status",
            "acknowledged_by",
            "acknowledged_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]

    def get_reported_by_name(self, obj):
        if not obj.reported_by_id:
            return None
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        return (
            Staffcreation.objects.filter(staff_unique_id=obj.reported_by_id)
            .values_list("employee_name", flat=True)
            .first()
        )

    def validate_trip_assignment_id(self, value):
        # Admin web form can pick any trip; a delay on a closed trip is noise.
        assignment = DailyTripAssignment.objects.filter(unique_id=value).first()
        if assignment and assignment.status in (
            DailyTripAssignment.STATUS_COMPLETED,
            DailyTripAssignment.STATUS_CANCELLED,
        ):
            raise serializers.ValidationError(
                "Cannot report a delay for a completed or cancelled trip."
            )
        return value

    def validate_delay_remarks(self, value):
        # The remarks ARE the feature — a delay with no explanation tells the
        # supervisor nothing, so an all-whitespace value is rejected here
        # rather than being stored as blank.
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError(
                "Describe what caused the delay."
            )
        return cleaned


class TripDelayAcknowledgeSerializer(serializers.Serializer):
    supervisor_remarks = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
