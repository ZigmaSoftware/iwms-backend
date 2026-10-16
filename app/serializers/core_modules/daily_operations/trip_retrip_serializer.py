from django.utils import timezone
from rest_framework import serializers

from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.panchayat import Panchayat
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.services.retrip_service import build_pending_snapshot
from app.services.retrip_timeout_service import deadline_for


class TripRetripRequestSerializer(serializers.ModelSerializer):
    """Everything a supervisor/admin needs to decide, in one payload.

    `pending_snapshot` is what was outstanding when the request was raised;
    `live_pending` is recomputed on read, because a colleague may have
    collected a stop since — approval must tick boxes against reality, not
    history.
    """

    assignment_unique_id = serializers.CharField(source="assignment_id", read_only=True)
    trip_date = serializers.DateField(source="assignment.trip_date", read_only=True, default=None)
    scheduled_time = serializers.TimeField(source="assignment.scheduled_time", read_only=True, default=None)
    assignment_status = serializers.CharField(source="assignment.status", read_only=True, default=None)
    collection_type = serializers.SerializerMethodField()
    vehicle_no = serializers.SerializerMethodField()
    area_name = serializers.SerializerMethodField()
    requested_by_name = serializers.CharField(
        source="requested_by.employee_name", read_only=True, default=None
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.employee_name", read_only=True, default=None
    )
    live_pending = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()
    urgency = serializers.SerializerMethodField()

    class Meta:
        model = TripRetripRequest
        fields = "__all__"
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def get_collection_type(self, obj):
        assignment = obj.assignment
        plan_id = getattr(assignment, "trip_plan_id", None) if assignment else None
        plan = TripPlan.objects.filter(unique_id=plan_id).first() if plan_id else None
        return getattr(plan, "collection_type", None)

    def get_vehicle_no(self, obj):
        assignment = obj.assignment
        vehicle_id = getattr(assignment, "vehicle_id", None) if assignment else None
        vehicle = (
            VehicleCreation.objects.filter(unique_id=vehicle_id).first()
            if vehicle_id
            else None
        )
        return getattr(vehicle, "vehicle_no", None)

    def get_area_name(self, obj):
        assignment = obj.assignment
        if assignment is None:
            return None
        ward = assignment.wards.first()
        if ward is not None:
            return ward.ward_name
        panchayat = (
            Panchayat.objects.filter(unique_id=assignment.panchayat_id).first()
            if assignment.panchayat_id
            else None
        )
        return getattr(panchayat, "panchayat_name", None)

    def get_live_pending(self, obj):
        assignment = obj.assignment
        if assignment is None:
            return None
        return build_pending_snapshot(assignment)

    def get_time_remaining_seconds(self, obj):
        if not obj.is_pending:
            return 0
        return max(0, int((deadline_for(obj) - timezone.now()).total_seconds()))

    def get_urgency(self, obj):
        if not obj.is_pending:
            return "expired" if obj.status == obj.STATUS_EXPIRED else "decided"
        seconds = self.get_time_remaining_seconds(obj)
        if seconds <= 10 * 60:
            return "urgent"
        if seconds <= 20 * 60:
            return "reminder"
        return "normal"
