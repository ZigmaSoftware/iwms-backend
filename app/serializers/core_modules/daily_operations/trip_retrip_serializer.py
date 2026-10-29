from django.utils import timezone
from rest_framework import serializers

from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.panchayat import Panchayat
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.services.retrip_service import build_pending_snapshot, build_pending_snapshots
from app.services.retrip_timeout_service import deadline_for
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.related_prefetch import cached_related, prefetch_related_rows, related

RETRIP_LOOKUPS = {
    "assignment": (DailyTripAssignment, "assignment_id"),
    "requested_by": (Staffcreation, "requested_by_id", "staff_unique_id"),
    "reviewed_by": (Staffcreation, "reviewed_by_id", "staff_unique_id"),
}
ASSIGNMENT_LOOKUPS = {
    "trip_plan": (TripPlan, "trip_plan_id"),
    "vehicle": (VehicleCreation, "vehicle_id"),
    "panchayat": (Panchayat, "panchayat_id"),
}
TRIP_PLAN_LOOKUPS = {"zone": (Zone, "zone_id")}


def attach_wards(objs):
    """Load `obj.wards` (Ward rows of a comma-separated `ward_ids`) for many
    objects in one query, in primary-key order like `wards.first()`."""
    objs = [obj for obj in objs if obj is not None]
    ids = {w for obj in objs for w in obj.get_ward_ids()}
    rows = list(Ward.objects.filter(unique_id__in=ids).order_by("unique_id")) if ids else []
    for obj in objs:
        wanted = set(obj.get_ward_ids())
        obj._ward_rows = [ward for ward in rows if ward.unique_id in wanted]
    return rows


def _first_ward(obj):
    rows = getattr(obj, "_ward_rows", None)
    if rows is None:
        return obj.wards.first()
    return rows[0] if rows else None


def _all_wards(obj):
    rows = getattr(obj, "_ward_rows", None)
    return obj.wards.all() if rows is None else rows


def pending_snapshots_for(assignments):
    """`build_pending_snapshot` for many assignments: {assignment unique_id: snapshot}."""
    return build_pending_snapshots(assignments)


def pending_snapshot(assignment):
    """Snapshot attached by `pending_snapshots_for`, else computed on its own."""
    snapshot = getattr(assignment, "_pending_snapshot", None)
    return snapshot if snapshot is not None else build_pending_snapshot(assignment)


class TripRetripRequestListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        instances = list(data.all() if hasattr(data, "all") else data)
        rows = prefetch_related_rows(instances, RETRIP_LOOKUPS)
        assignments = list(rows["assignment"].values())
        assignment_rows = prefetch_related_rows(assignments, ASSIGNMENT_LOOKUPS)
        plans = list(assignment_rows["trip_plan"].values())
        prefetch_related_rows(plans, TRIP_PLAN_LOOKUPS)
        wards = attach_wards([*assignments, *plans])
        prefetch_related_rows(wards, {"zone": (Zone, "zone_id")})
        snapshots = pending_snapshots_for(assignments)
        for assignment in assignments:
            assignment._pending_snapshot = snapshots[assignment.unique_id]
        return super().to_representation(instances)


class TripRetripRequestSerializer(serializers.ModelSerializer):
    """Everything a supervisor/admin needs to decide, in one payload.

    `pending_snapshot` is what was outstanding when the request was raised;
    `live_pending` is recomputed on read, because a colleague may have
    collected a stop since — approval must tick boxes against reality, not
    history.
    """

    assignment_unique_id = serializers.CharField(source="assignment_id", read_only=True)
    trip_date = serializers.DateField(source="_assignment_row.trip_date", read_only=True, default=None)
    scheduled_time = serializers.TimeField(source="_assignment_row.scheduled_time", read_only=True, default=None)
    assignment_status = serializers.CharField(source="_assignment_row.status", read_only=True, default=None)
    collection_type = serializers.SerializerMethodField()
    vehicle_no = serializers.SerializerMethodField()
    area_name = serializers.SerializerMethodField()
    panchayat_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    requested_by_name = serializers.CharField(
        source="_requested_by_row.employee_name", read_only=True, default=None
    )
    reviewed_by_name = serializers.CharField(
        source="_reviewed_by_row.employee_name", read_only=True, default=None
    )
    reason_code_label = serializers.CharField(
        source="get_reason_code_display", read_only=True, default=None
    )
    live_pending = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()
    urgency = serializers.SerializerMethodField()

    class Meta:
        model = TripRetripRequest
        fields = "__all__"
        read_only_fields = ["unique_id", "created_at", "updated_at"]
        list_serializer_class = TripRetripRequestListSerializer

    def to_representation(self, instance):
        # Plain attributes for the dotted `source=` fields above, so they read
        # the prefetched (or once-looked-up) rows instead of the properties.
        instance._assignment_row = cached_related(instance, "assignment")
        instance._requested_by_row = cached_related(instance, "requested_by")
        instance._reviewed_by_row = cached_related(instance, "reviewed_by")
        return super().to_representation(instance)

    def get_collection_type(self, obj):
        assignment = cached_related(obj, "assignment")
        plan_id = getattr(assignment, "trip_plan_id", None) if assignment else None
        plan = related(assignment, "trip_plan", TripPlan, "trip_plan_id") if plan_id else None
        return getattr(plan, "collection_type", None)

    def get_vehicle_no(self, obj):
        assignment = cached_related(obj, "assignment")
        vehicle_id = getattr(assignment, "vehicle_id", None) if assignment else None
        vehicle = (
            related(assignment, "vehicle", VehicleCreation, "vehicle_id")
            if vehicle_id
            else None
        )
        return getattr(vehicle, "vehicle_no", None)

    def get_area_name(self, obj):
        assignment = cached_related(obj, "assignment")
        if assignment is None:
            return None
        ward = _first_ward(assignment)
        if ward is not None:
            return ward.ward_name
        panchayat = (
            related(assignment, "panchayat", Panchayat, "panchayat_id")
            if assignment.panchayat_id
            else None
        )
        return getattr(panchayat, "panchayat_name", None)

    # Location split by level (area_name above collapses ward/panchayat into one
    # unlabeled name) — same zone lookup order as DailyTripAssignmentSerializer.
    def get_panchayat_name(self, obj):
        assignment = cached_related(obj, "assignment")
        panchayat = related(assignment, "panchayat") if assignment else None
        return getattr(panchayat, "panchayat_name", None)

    def get_zone_name(self, obj):
        assignment = cached_related(obj, "assignment")
        if assignment is None:
            return None
        plan = related(assignment, "trip_plan")
        zone = related(plan, "zone") if plan else None
        if zone is None:
            ward = _first_ward(assignment) or (_first_ward(plan) if plan else None)
            zone = related(ward, "zone") if ward else None
        return getattr(zone, "zone_name", None)

    def get_ward_name(self, obj):
        assignment = cached_related(obj, "assignment")
        if assignment is None:
            return None
        names = [ward.ward_name for ward in _all_wards(assignment)]
        return ", ".join(names) or None

    def get_live_pending(self, obj):
        assignment = cached_related(obj, "assignment")
        if assignment is None:
            return None
        return pending_snapshot(assignment)

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
