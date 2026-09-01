from rest_framework import serializers

from app.models.schedule_masters.trip_delay_report import TripDelayReport
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment


class TripDelayReportSerializer(serializers.ModelSerializer):
    """Read/write for the delay log.

    The driver supplies only `trip_assignment_id`, `delay_reason` and
    `delay_remarks` (plus optional minutes/location). Everything else —
    tenant scope, reporter, timestamps, status — is stamped server-side, so a
    client cannot report a delay against another crew's trip or backdate one.
    """

    trip_assignment_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )

    # Flattened read-only context so the supervisor list needs no extra calls.
    delay_reason_display = serializers.CharField(
        source="get_delay_reason_display", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    reported_by_name = serializers.CharField(
        source="reported_by.employee_name", read_only=True, default=None
    )
    vehicle_no = serializers.CharField(
        source="trip_assignment_id.vehicle_id.vehicle_no",
        read_only=True,
        default=None,
    )
    trip_date = serializers.DateField(
        source="trip_assignment_id.trip_date", read_only=True
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
