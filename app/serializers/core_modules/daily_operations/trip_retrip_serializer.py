from rest_framework import serializers

from app.models.schedule_masters.trip_retrip_request import TripRetripRequest
from app.services.retrip_service import build_pending_snapshot


class TripRetripRequestSerializer(serializers.ModelSerializer):
    """Everything a supervisor/admin needs to decide, in one payload.

    `pending_snapshot` is what was outstanding when the request was raised;
    `live_pending` is recomputed on read, because a colleague may have
    collected a stop since — approval must tick boxes against reality, not
    history.
    """

    assignment_unique_id = serializers.CharField(source="assignment.unique_id", read_only=True)
    trip_date = serializers.DateField(source="assignment.trip_date", read_only=True)
    scheduled_time = serializers.TimeField(source="assignment.scheduled_time", read_only=True)
    assignment_status = serializers.CharField(source="assignment.status", read_only=True)
    collection_type = serializers.SerializerMethodField()
    vehicle_no = serializers.CharField(source="assignment.vehicle_id.vehicle_no", read_only=True)
    area_name = serializers.SerializerMethodField()
    requested_by_name = serializers.CharField(
        source="requested_by.employee_name", read_only=True, default=None
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.employee_name", read_only=True, default=None
    )
    live_pending = serializers.SerializerMethodField()

    class Meta:
        model = TripRetripRequest
        fields = "__all__"
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def get_collection_type(self, obj):
        plan = getattr(obj.assignment, "trip_plan_id", None)
        return getattr(plan, "collection_type", None)

    def get_area_name(self, obj):
        assignment = obj.assignment
        ward = assignment.wards.first()
        if ward is not None:
            return ward.ward_name
        panchayat = assignment.panchayat_id
        return getattr(panchayat, "panchayat_name", None)

    def get_live_pending(self, obj):
        return build_pending_snapshot(obj.assignment)
