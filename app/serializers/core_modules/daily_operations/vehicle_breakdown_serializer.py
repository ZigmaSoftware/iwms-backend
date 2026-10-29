from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.utils import timezone
from rest_framework import serializers

from app.models.core_modules.daily_operations.vehicle_breakdown import (
    VehicleBreakdown,
    sync_vehicle_operational_status,
)
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.panchayat import Panchayat
from app.utils.related_prefetch import cached_related, prefetch_related_rows, related

BREAKDOWN_LOOKUPS = {
    "trip_assignment": (DailyTripAssignment, "trip_assignment_id"),
    "breakdown_vehicle": (VehicleCreation, "breakdown_vehicle_id"),
    "replacement_vehicle": (VehicleCreation, "replacement_vehicle_id"),
    "replacement_driver": (Staffcreation, "replacement_driver_id", "staff_unique_id"),
    "replacement_operator": (Staffcreation, "replacement_operator_id", "staff_unique_id"),
    "alt_staff_template": (AlternativeStaffTemplate, "alt_staff_template_id"),
    "approved_by_user": (Staffcreation, "approved_by", "staff_unique_id"),
    "repaired_by_staff": (Staffcreation, "repaired_by", "staff_unique_id"),
}
ASSIGNMENT_LOOKUPS = {
    "trip_plan": (TripPlan, "trip_plan_id"),
    "panchayat": (Panchayat, "panchayat_id"),
    "alt_staff_template": (AlternativeStaffTemplate, "alt_staff_template_id"),
    "staff_template": (StaffTemplate, "staff_template_id"),
}
TRIP_PLAN_LOOKUPS = {"staff_template": (StaffTemplate, "staff_template_id")}
CREW_LOOKUPS = {
    "driver": (Staffcreation, "driver_id", "staff_unique_id"),
    "operator": (Staffcreation, "operator_id", "staff_unique_id"),
}


class VehicleBreakdownListSerializer(serializers.ListSerializer):
    """Loads every relation the detail fields read once for the whole page."""

    def to_representation(self, data):
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdownPhoto

        instances = list(data.all() if hasattr(data, "all") else data)
        rows = prefetch_related_rows(instances, BREAKDOWN_LOOKUPS)
        assignments = list(rows["trip_assignment"].values())
        assignment_rows = prefetch_related_rows(assignments, ASSIGNMENT_LOOKUPS)
        plans = list(assignment_rows["trip_plan"].values())
        plan_rows = prefetch_related_rows(plans, TRIP_PLAN_LOOKUPS)
        prefetch_related_rows(
            [
                *rows["alt_staff_template"].values(),
                *assignment_rows["alt_staff_template"].values(),
                *assignment_rows["staff_template"].values(),
                *plan_rows["staff_template"].values(),
            ],
            CREW_LOOKUPS,
        )

        from app.serializers.core_modules.daily_operations.trip_retrip_serializer import (
            pending_snapshots_for,
        )

        # Only trips without a replacement yet show pending stops.
        open_assignments = [
            assignment for obj in instances if not obj.new_assignment
            for assignment in [obj._related_cache["trip_assignment"]] if assignment
        ]
        snapshots = pending_snapshots_for(open_assignments)
        for assignment in open_assignments:
            assignment._pending_snapshot = snapshots[assignment.unique_id]

        photos = {}
        ids = [obj.unique_id for obj in instances]
        if ids:
            # Keep the query's row order within each breakdown.
            for photo in VehicleBreakdownPhoto.objects.filter(breakdown_id__in=ids):
                photos.setdefault(photo.breakdown_id, []).append(photo)
        for obj in instances:
            obj._photos = photos.get(obj.unique_id, [])
        return super().to_representation(instances)


def _ensure_vehicle_in_service(vehicle):
    """A vehicle that is itself broken down cannot be the replacement."""
    vehicle_id = vehicle if isinstance(vehicle, str) else getattr(vehicle, "unique_id", None)
    if VehicleCreation.objects.filter(
        unique_id=vehicle_id,
        operational_status=VehicleCreation.OperationalStatus.BREAKDOWN,
    ).exists():
        raise serializers.ValidationError(
            {"replacement_vehicle_id": "Replacement vehicle is under breakdown."}
        )


def upcoming_trips_of_broken_vehicle(breakdown):
    """The broken vehicle's other trips that have not started yet — from the
    breakdown's trip date onwards (later trips today, and any already created
    for later dates). These are what /verify/ can move to the replacement."""
    source = breakdown.trip_assignment
    from_date = source.trip_date if source else timezone.localdate()
    qs = DailyTripAssignment.objects.filter(
        vehicle_id=breakdown.breakdown_vehicle_id,
        status=DailyTripAssignment.STATUS_SCHEDULED,
        actual_start_at__isnull=True,
        trip_date__gte=from_date,
        is_deleted=False,
    )
    if source:
        qs = qs.exclude(pk=source.pk)
    return qs.order_by("trip_date", "scheduled_time", "created_at")


def original_crew_template(breakdown):
    """The crew on the trip when it broke down: the trip's alternative crew
    if one was substituted in, else the plan's / trip's own staff template."""
    assignment = breakdown.trip_assignment
    if not assignment:
        return None
    trip_plan = assignment.trip_plan
    return (
        assignment.alt_staff_template
        or (trip_plan.staff_template if trip_plan else None)
        or assignment.staff_template
    )


def move_trips_to_vehicle(trips, replacement_vehicle_id, *, exclude_ids, now):
    """Point each trip at the replacement vehicle unless that vehicle already
    has another unfinished trip at the same date and time. Returns
    (moved_ids, skipped) where skipped is [{"trip_id", "reason"}]."""
    moved, skipped = [], []
    for trip in trips:
        clash = (
            DailyTripAssignment.objects.filter(
                vehicle_id=replacement_vehicle_id,
                trip_date=trip.trip_date,
                scheduled_time=trip.scheduled_time,
                status__in=[
                    DailyTripAssignment.STATUS_SCHEDULED,
                    DailyTripAssignment.STATUS_IN_PROGRESS,
                ],
                is_deleted=False,
            )
            .exclude(unique_id__in=[trip.unique_id, *exclude_ids])
            .first()
        )
        if clash:
            skipped.append({
                "trip_id": trip.unique_id,
                "reason": (
                    f"Replacement vehicle already has trip {clash.unique_id} "
                    f"on {trip.trip_date} at {trip.scheduled_time}."
                ),
            })
            continue
        DailyTripAssignment.objects.filter(pk=trip.pk).update(
            vehicle_id=replacement_vehicle_id, updated_at=now,
        )
        moved.append(trip.unique_id)
    return moved, skipped
class CoordinateField(serializers.DecimalField):
    """Latitude/longitude rounded to 7 decimal places before validation."""

    def __init__(self, **kwargs):
        super().__init__(max_digits=10, decimal_places=7, **kwargs)

    def to_internal_value(self, data):
        if data not in (None, ""):
            try:
                data = Decimal(str(data).strip()).quantize(
                    Decimal("0.0000001"), rounding=ROUND_HALF_UP
                )
            except (InvalidOperation, ValueError):
                pass  # let DecimalField report "A valid number is required."
        return super().to_internal_value(data)


class VehicleBreakdownSerializer(serializers.ModelSerializer):

    # Tenancy write inputs (resolved by CompanyScopedViewSet.perform_create)
    company_id_input = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    project_id_input = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )

    # Trip assignments have no separate name, so they stay ID-based.
    trip_assignment_id = UniqueIdOrPkField(
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    # Vehicles/staff accept either their unique_id or their human-readable
    # vehicle number / employee name (e.g. Excel upload column "TN01AB1234"
    # or "Ramesh Kumar" instead of the opaque VEH-xxxx / STAFF-xxxx id).
    breakdown_vehicle_id = NameOrUniqueIdField(
        name_field="vehicle_no",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
    )
    # Optional on create — the driver reporting a breakdown usually doesn't
    # know the replacement yet; the supervisor picks these at `/verify/`
    # (see VehicleBreakdownVerifySerializer below), which then requires all
    # three be set (from here or there) before approving.
    replacement_vehicle_id = NameOrUniqueIdField(
        name_field="vehicle_no",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    replacement_driver_id = NameOrUniqueIdField(
        name_field="employee_name",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    replacement_operator_id = NameOrUniqueIdField(
        name_field="employee_name",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    # Read-only detail fields
    trip_assignment_detail = serializers.SerializerMethodField(read_only=True)
    # Phone GPS reports 12+ decimal places; round to what the column stores
    # instead of rejecting the report.
    breakdown_lat = CoordinateField(required=False, allow_null=True)
    breakdown_lng = CoordinateField(required=False, allow_null=True)
    breakdown_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_driver_detail = serializers.SerializerMethodField(read_only=True)
    replacement_operator_detail = serializers.SerializerMethodField(read_only=True)
    original_driver_detail = serializers.SerializerMethodField(read_only=True)
    original_operator_detail = serializers.SerializerMethodField(read_only=True)
    alt_staff_template_detail = serializers.SerializerMethodField(read_only=True)
    approved_by_detail = serializers.SerializerMethodField(read_only=True)
    repaired_by_detail = serializers.SerializerMethodField(read_only=True)
    breakdown_vehicle_operational_status = serializers.SerializerMethodField(read_only=True)
    photos = serializers.SerializerMethodField(read_only=True)
    new_assignment_id = serializers.SerializerMethodField(read_only=True)
    pending_stops = serializers.SerializerMethodField(read_only=True)
    upcoming_trips = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VehicleBreakdown
        fields = [
            "unique_id",
            "company_id",
            "project_id",
            "company_id_input",
            "project_id_input",
            "trip_assignment_id",
            "trip_assignment_detail",
            "breakdown_vehicle_id",
            "breakdown_vehicle_detail",
            "replacement_vehicle_id",
            "replacement_vehicle_detail",
            "replacement_driver_id",
            "replacement_driver_detail",
            "replacement_operator_id",
            "replacement_operator_detail",
            "original_driver_detail",
            "original_operator_detail",
            "alt_staff_template_id",
            "alt_staff_template_detail",
            "breakdown_time",
            "breakdown_lat",
            "breakdown_lng",
            "breakdown_location",
            "collected_weight_before_breakdown_kg",
            "breakdown_reason",
            "breakdown_remarks",
            "status",
            "approval_status",
            "approved_by",
            "approved_by_detail",
            "approved_at",
            "rejection_remarks",
            "repaired_at",
            "repaired_by",
            "repaired_by_detail",
            "repair_remarks",
            "breakdown_vehicle_operational_status",
            "photos",
            "new_assignment_id",
            "pending_stops",
            "upcoming_trips",
            "moved_assignment_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "company_id",
            "project_id",
            "alt_staff_template_id",
            "alt_staff_template_detail",
            "status",
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_remarks",
            "repaired_at",
            "repaired_by",
            "repair_remarks",
            "new_assignment_id",
            "pending_stops",
            "upcoming_trips",
            "moved_assignment_ids",
            "created_at",
            "updated_at",
        ]
        list_serializer_class = VehicleBreakdownListSerializer

    # ── Validation ───────────────────────────────────────────────────

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        # The id fields resolve to unique_id strings (backing columns are
        # CharFields), so load the assignment row for the checks below.
        assignment_id = attrs.get("trip_assignment_id")
        assignment = (
            DailyTripAssignment.objects.filter(unique_id=assignment_id).first()
            if assignment_id
            else None
        )
        if assignment:
            request = self.context.get("request")
            user = getattr(request, "user", None)
            if user and not getattr(user, "is_superuser", False):
                user_company_id = getattr(user, "company_id", None)
                user_project_id = getattr(user, "project_id", None)
                if (
                    assignment.company_id != user_company_id
                    or assignment.project_id != user_project_id
                ):
                    raise serializers.ValidationError(
                        {"trip_assignment_id": "Trip assignment is outside your company or project."}
                    )

            if assignment.status in [
                DailyTripAssignment.STATUS_COMPLETED,
                DailyTripAssignment.STATUS_CANCELLED,
            ]:
                raise serializers.ValidationError(
                    {"trip_assignment_id": "Cannot log a breakdown for a completed or cancelled trip."}
                )

            reported_vehicle_id = attrs.get("breakdown_vehicle_id")
            if reported_vehicle_id and reported_vehicle_id != assignment.vehicle_id:
                raise serializers.ValidationError(
                    {"breakdown_vehicle_id": "Vehicle does not belong to this trip assignment."}
                )
            # The assignment is authoritative. This also keeps older mobile
            # clients working when their cached trip payload omits the vehicle.
            attrs["breakdown_vehicle_id"] = assignment.vehicle_id

        repl = attrs.get("replacement_vehicle_id")
        orig = attrs.get("breakdown_vehicle_id")
        if repl and orig and repl == orig:
            raise serializers.ValidationError(
                {"replacement_vehicle_id": "Replacement vehicle must be different from the broken vehicle."}
            )
        if repl:
            _ensure_vehicle_in_service(repl)

        if assignment and repl:
            conflict = DailyTripAssignment.objects.filter(
                vehicle_id=repl,
                trip_date=assignment.trip_date,
                status__in=[
                    DailyTripAssignment.STATUS_SCHEDULED,
                    DailyTripAssignment.STATUS_IN_PROGRESS,
                ],
                is_deleted=False,
            ).exclude(pk=assignment.pk).exists()
            if conflict:
                raise serializers.ValidationError(
                    {
                        "replacement_vehicle_id": (
                            f"Replacement vehicle is already assigned to another active trip on {assignment.trip_date}."
                        )
                    }
                )

        return attrs

    # ── Detail helpers ───────────────────────────────────────────────

    def _staff_dict(self, staff):
        if not staff:
            return None
        return {
            "unique_id": staff.staff_unique_id,
            "name": staff.employee_name,
        }

    def _vehicle_dict(self, vehicle):
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": str(vehicle.capacity) if vehicle.capacity else None,
        }

    def _alt_staff_template_dict(self, template):
        if not template:
            return None
        return {
            "unique_id": template.unique_id,
            "display_code": template.display_code,
            "base_staff_template_id": getattr(template, "staff_template_id", None),
            "driver": self._staff_dict(related(template, "driver")),
            "operator": self._staff_dict(related(template, "operator")),
            "change_reason": template.change_reason,
            "change_remarks": template.change_remarks,
            "approval_status": template.approval_status,
        }

    # All relation columns on VehicleBreakdown / DailyTripAssignment /
    # TripPlan are plain id strings — the model properties resolve the rows.

    def _crew_template(self, obj):
        # Same as original_crew_template(), reading prefetched rows.
        assignment = cached_related(obj, "trip_assignment")
        if not assignment:
            return None
        trip_plan = related(assignment, "trip_plan")
        return (
            related(assignment, "alt_staff_template")
            or (related(trip_plan, "staff_template") if trip_plan else None)
            or related(assignment, "staff_template")
        )

    def get_trip_assignment_detail(self, obj):
        a = cached_related(obj, "trip_assignment")
        if not a:
            return None
        panchayat = related(a, "panchayat")
        trip_plan = related(a, "trip_plan")
        return {
            "unique_id": a.unique_id,
            "trip_date": str(a.trip_date),
            "status": a.status,
            "scheduled_time": str(a.scheduled_time) if a.scheduled_time else None,
            "panchayat_name": panchayat.panchayat_name if panchayat else None,
            "trip_plan_display_code": trip_plan.display_code if trip_plan else None,
        }

    def get_breakdown_vehicle_detail(self, obj):
        return self._vehicle_dict(related(obj, "breakdown_vehicle"))

    def get_replacement_vehicle_detail(self, obj):
        return self._vehicle_dict(related(obj, "replacement_vehicle"))

    def get_replacement_driver_detail(self, obj):
        return self._staff_dict(related(obj, "replacement_driver"))

    def get_replacement_operator_detail(self, obj):
        return self._staff_dict(related(obj, "replacement_operator"))

    def get_original_driver_detail(self, obj):
        template = self._crew_template(obj)
        return self._staff_dict(related(template, "driver")) if template else None

    def get_original_operator_detail(self, obj):
        template = self._crew_template(obj)
        return self._staff_dict(related(template, "operator")) if template else None

    def get_alt_staff_template_detail(self, obj):
        return self._alt_staff_template_dict(related(obj, "alt_staff_template"))

    def get_approved_by_detail(self, obj):
        return self._staff_dict(related(obj, "approved_by_user"))

    def get_repaired_by_detail(self, obj):
        if not obj.repaired_by:
            return None
        cache = getattr(obj, "_related_cache", None) or {}
        if "repaired_by_staff" in cache:
            return self._staff_dict(cache["repaired_by_staff"])
        return self._staff_dict(
            Staffcreation.objects.filter(staff_unique_id=obj.repaired_by).first()
        )

    def get_breakdown_vehicle_operational_status(self, obj):
        vehicle = related(obj, "breakdown_vehicle")
        return vehicle.operational_status if vehicle else None

    def get_new_assignment_id(self, obj):
        return obj.new_assignment or None

    def get_upcoming_trips(self, obj):
        """Only while the breakdown awaits approval — that is when the
        supervisor picks which of these move to the replacement vehicle."""
        if obj.approval_status != VehicleBreakdown.APPROVAL_PENDING:
            return []
        return [
            {
                "unique_id": trip.unique_id,
                "trip_date": str(trip.trip_date),
                "scheduled_time": str(trip.scheduled_time) if trip.scheduled_time else None,
                "trip_plan_display_code": getattr(trip.trip_plan, "display_code", None),
            }
            for trip in upcoming_trips_of_broken_vehicle(obj)
        ]

    def get_pending_stops(self, obj):
        """What's still outstanding on the trip being broken down — bin
        collection points for a bin trip (supervisor picks which carry over
        at /verify/), or un-collected houses for a household trip (all of
        them auto-carry). Not shown once a replacement trip already exists."""
        assignment = cached_related(obj, "trip_assignment")
        if not assignment or obj.new_assignment:
            return None
        from app.serializers.core_modules.daily_operations.trip_retrip_serializer import (
            pending_snapshot,
        )

        return pending_snapshot(assignment)

    def get_photos(self, obj):
        request = self.context.get("request")
        photos = []
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdownPhoto

        rows = getattr(obj, "_photos", None)
        if rows is None:
            rows = VehicleBreakdownPhoto.objects.filter(breakdown_id=obj.unique_id)
        for photo in rows:
            url = photo.photo.url if photo.photo else None
            if url and request is not None:
                url = request.build_absolute_uri(url)
            photos.append({"id": photo.pk, "photo": url, "uploaded_at": photo.uploaded_at})
        return photos


class VehicleBreakdownVerifySerializer(serializers.Serializer):
    """Used for PATCH /{id}/verify/ — the supervisor picks the replacement
    vehicle/driver/operator here (if not already set at creation) and
    approves the breakdown."""
    remarks = serializers.CharField(required=False, allow_blank=True, default="")
    replacement_vehicle_id = NameOrUniqueIdField(
        name_field="vehicle_no",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    replacement_driver_id = NameOrUniqueIdField(
        name_field="employee_name",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    replacement_operator_id = NameOrUniqueIdField(
        name_field="employee_name",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    # Optional for API/web clients that offer per-stop selection. The mobile
    # replacement sheet does not, so omitting it carries every pending stop.
    collection_point_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    # Which of the broken vehicle's upcoming trips also move to the
    # replacement. Omitted = none of them: the mobile sheet has no picker,
    # and moving blindly could overload the replacement — the trips stay
    # flagged on the broken vehicle for the supervisor to move on the web.
    move_assignment_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    # Which of the broken vehicle's trip plans run on the replacement from
    # the next day until it is repaired. Omitted = every plan the
    # replacement has no clashing regular work for (see verify_preview).
    substitute_plan_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )

    @staticmethod
    def _staff_id(value):
        if value is None or isinstance(value, str):
            return value or None
        return getattr(value, "staff_unique_id", None)

    def validate(self, attrs):
        instance = self.context["instance"]
        assignment = instance.trip_assignment
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if assignment is None:
            raise serializers.ValidationError(
                "The trip for this breakdown no longer exists."
            )

        driver_id = self._staff_id(attrs.get("replacement_driver_id"))
        operator_id = self._staff_id(attrs.get("replacement_operator_id"))
        # Nobody picked (here or when reporting): the same crew carries on
        # with the replacement vehicle.
        crew = original_crew_template(instance)
        if not driver_id and not instance.replacement_driver_id and crew:
            driver_id = crew.driver_id
            attrs["replacement_driver_id"] = driver_id
        if not operator_id and not instance.replacement_operator_id and crew:
            operator_id = crew.operator_id
            attrs["replacement_operator_id"] = operator_id
        selected_ids = {staff_id for staff_id in [driver_id, operator_id] if staff_id}

        role_name = (getattr(getattr(user, "staffusertype", None), "name", "") or "").lower()
        if "supervisor" in role_name:
            from django.db.models import Q
            from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan

            supervisor_id = user.staff_unique_id
            if getattr(assignment.trip_plan, "supervisor_id", None) != supervisor_id:
                raise serializers.ValidationError(
                    "You can only approve breakdowns from trips assigned to you."
                )

            supervised_template_ids = TripPlan.objects.filter(
                supervisor_id=supervisor_id,
                is_deleted=False,
            ).exclude(staff_template_id__isnull=True).values_list(
                "staff_template_id", flat=True
            )
            supervised_staff_ids = set(
                StaffTemplate.objects.filter(unique_id__in=supervised_template_ids)
                .exclude(driver_id__isnull=True)
                .values_list("driver_id", flat=True)
            ) | set(
                StaffTemplate.objects.filter(unique_id__in=supervised_template_ids)
                .exclude(operator_id__isnull=True)
                .values_list("operator_id", flat=True)
            )
            allowed_ids = set(
                Staffcreation.objects.filter(
                    Q(staff_head_id=supervisor_id)
                    | Q(staff_unique_id__in=supervised_staff_ids),
                    company_id=assignment.company_id,
                    project_id=assignment.project_id,
                    is_deleted=False,
                    active_status=True,
                ).values_list("staff_unique_id", flat=True)
            )
            if not selected_ids.issubset(allowed_ids):
                raise serializers.ValidationError(
                    "Replacement staff must report to the trip supervisor."
                )

        busy_assignments = DailyTripAssignment.objects.filter(
            company_id=assignment.company_id,
            project_id=assignment.project_id,
            trip_date=assignment.trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        ).exclude(pk=assignment.pk).exclude(
            # The broken vehicle's own later trips are this crew's next jobs,
            # done one after another — they don't stop the same crew from
            # carrying on with the replacement vehicle.
            pk__in=upcoming_trips_of_broken_vehicle(instance).values("pk"),
        )
        busy_driver_ids = set()
        busy_operator_ids = set()
        for busy_assignment in busy_assignments:
            template = busy_assignment.alt_staff_template or busy_assignment.staff_template
            if template:
                if template.driver_id:
                    busy_driver_ids.add(template.driver_id)
                if template.operator_id:
                    busy_operator_ids.add(template.operator_id)
        if driver_id in busy_driver_ids:
            raise serializers.ValidationError(
                {"replacement_driver_id": "Driver is already assigned to another active trip."}
            )
        if operator_id in busy_operator_ids:
            raise serializers.ValidationError(
                {"replacement_operator_id": "Operator is already assigned to another active trip."}
            )

        return attrs

    def save(self):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks", "")
        now = timezone.now()

        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            raise serializers.ValidationError("Breakdown has already been approved.")
        if instance.approval_status == VehicleBreakdown.APPROVAL_REJECTED:
            raise serializers.ValidationError("Rejected breakdowns cannot be approved.")

        # This plain Serializer has no Meta.model, so NameOrUniqueIdField
        # hands back model instances; the VehicleBreakdown columns are id
        # strings. Normalise both to the id string.
        def _ref(value, id_attr):
            if value is None or isinstance(value, str):
                return value or None
            return getattr(value, id_attr, None)

        # Only fill in what the driver didn't already set at creation —
        # never overwrite an explicit earlier choice.
        replacement_vehicle = (
            _ref(self.validated_data.get("replacement_vehicle_id"), "unique_id")
            or instance.replacement_vehicle_id
        )
        replacement_driver = (
            _ref(self.validated_data.get("replacement_driver_id"), "staff_unique_id")
            or instance.replacement_driver_id
        )
        replacement_operator = (
            _ref(self.validated_data.get("replacement_operator_id"), "staff_unique_id")
            or instance.replacement_operator_id
        )
        if not (replacement_vehicle and replacement_driver and replacement_operator):
            raise serializers.ValidationError(
                "Select a replacement vehicle, driver, and operator before approving this breakdown."
            )
        _ensure_vehicle_in_service(replacement_vehicle)

        from django.db import transaction
        from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
        from app.services import retrip_service

        assignment = instance.trip_assignment
        if assignment is None:
            raise serializers.ValidationError("The trip for this breakdown no longer exists.")
        pending_bins = list(assignment.pending_bin_stops())
        pending_households = list(assignment.pending_household_stops())
        collection_point_ids = self.validated_data.get("collection_point_ids")
        if not pending_bins and not pending_households:
            raise serializers.ValidationError("There are no pending stops to carry over.")
        if collection_point_ids:
            pending_bin_ids = {stop.unique_id for stop in pending_bins}
            unknown = set(collection_point_ids) - pending_bin_ids
            if unknown:
                raise serializers.ValidationError(
                    {"collection_point_ids": "Selected collection point is not pending on this trip."}
                )

        from app.services import vehicle_substitution

        upcoming = list(upcoming_trips_of_broken_vehicle(instance))
        move_ids = set(self.validated_data.get("move_assignment_ids") or [])
        unknown = move_ids - {trip.unique_id for trip in upcoming}
        if unknown:
            raise serializers.ValidationError(
                {"move_assignment_ids": "Selected trip is not an upcoming trip of the broken vehicle."}
            )
        trips_to_move = [trip for trip in upcoming if trip.unique_id in move_ids]

        preview = vehicle_substitution.verify_preview(instance, replacement_vehicle)
        plan_ids = self.validated_data.get("substitute_plan_ids")
        if plan_ids is None:
            plan_ids = {p["trip_plan_id"] for p in preview["plans"] if p["default_substitute"]}
        else:
            plan_ids = set(plan_ids)
            unknown = plan_ids - {p["trip_plan_id"] for p in preview["plans"]}
            if unknown:
                raise serializers.ValidationError(
                    {"substitute_plan_ids": "Selected trip plan does not use the broken vehicle."}
                )
        plans_to_substitute = list(
            vehicle_substitution.plans_of_vehicle(instance.breakdown_vehicle_id).filter(
                unique_id__in=plan_ids,
            )
        )

        with transaction.atomic():
            # Always create a fresh AlternativeStaffTemplate for this
            # breakdown's replacement crew. A staff_template can accumulate
            # several of these over time (one per breakdown event) — reusing
            # a prior breakdown's row here would silently overwrite its
            # driver/operator, corrupting that earlier breakdown's history.
            alt_template = AlternativeStaffTemplate.objects.create(
                staff_template_id=assignment.staff_template_id,
                driver_id=replacement_driver,
                operator_id=replacement_operator,
                company_id=instance.company_id,
                project_id=instance.project_id,
                change_reason="Vehicle Breakdown",
                change_remarks=remarks or instance.breakdown_remarks or "",
            )

            # Open a continuation crewed by the replacement
            # vehicle/driver/operator, carrying over the pending
            # bin/household stops (same rules as Re-Trip). The source trip is
            # not completed here; verification only assigns the replacement.
            try:
                continuation = retrip_service.create_breakdown_continuation(
                    assignment,
                    vehicle_id=replacement_vehicle,
                    alt_staff_template_id=alt_template.unique_id,
                    collection_point_ids=collection_point_ids,
                )
            except ValueError as exc:
                raise serializers.ValidationError(str(exc)) from exc

            # The broken vehicle's later trips keep their own crew — only
            # the vehicle changes.
            moved_ids, skipped_moves = move_trips_to_vehicle(
                trips_to_move,
                replacement_vehicle,
                exclude_ids=[continuation.unique_id],
                now=now,
            )

            # From the next day until repaired, the broken vehicle's plans
            # run on the replacement with their own crew.
            substitutions = [
                vehicle_substitution.create_substitution(
                    plan,
                    replacement_vehicle,
                    preview["substitute_from_date"],
                    breakdown_id=instance.unique_id,
                )
                for plan in plans_to_substitute
            ]

            # Update the breakdown record
            approved_by_staff = None
            if account:
                try:
                    from app.models.superadmin.staff_management.staffcreation import Staffcreation
                    approved_by_staff = Staffcreation.objects.filter(
                        account=account
                    ).first()
                except Exception:
                    pass

            VehicleBreakdown.objects.filter(pk=instance.pk).update(
                replacement_vehicle_id=replacement_vehicle,
                replacement_driver_id=replacement_driver,
                replacement_operator_id=replacement_operator,
                alt_staff_template_id=alt_template.unique_id,
                new_assignment=continuation.unique_id,
                moved_assignment_ids=moved_ids,
                status=VehicleBreakdown.STATUS_REPLACEMENT_ARRANGED,
                approval_status=VehicleBreakdown.APPROVAL_APPROVED,
                approved_by=getattr(approved_by_staff, "staff_unique_id", None),
                approved_at=now,
                updated_at=now,
            )
            instance.refresh_from_db()
            # Not stored — returned once by the /verify/ response.
            instance.skipped_moves = skipped_moves
            instance.substituted_plan_ids = [s.trip_plan_id for s in substitutions]

            from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent

            BinCollectionEvent.objects.filter(
                trip_assignment_id=assignment.unique_id,
                is_deleted=False,
            ).update(
                vehicle_breakdown_id=instance.unique_id,
                updated_at=now,
            )

        from app.models.core_modules.notifications.staff_notification import StaffNotification
        from app.services.staff_notification_service import notify_staff

        driver = instance.replacement_driver
        if driver is not None:
            vehicle_no = getattr(instance.replacement_vehicle, "vehicle_no", None) or "a new vehicle"
            notify_staff(
                driver,
                StaffNotification.TYPE_VEHICLE_REPLACEMENT_APPROVED,
                title="Vehicle replaced",
                body=(
                    f"Trip {instance.trip_assignment_id} has a breakdown replacement. "
                    f"Your assigned trip {instance.new_assignment or ''} uses "
                    f"{vehicle_no}."
                ),
                data={
                    "vehicle_breakdown_id": instance.unique_id,
                    "trip_assignment_id": instance.trip_assignment_id,
                    "new_assignment_id": instance.new_assignment,
                },
            )

        return instance


class VehicleBreakdownRejectSerializer(serializers.Serializer):
    """Used for PATCH /{id}/reject/ — rejects the breakdown request."""
    rejection_remarks = serializers.CharField(required=True)

    def save(self):
        instance = self.context["instance"]
        now = timezone.now()

        if instance.approval_status != VehicleBreakdown.APPROVAL_PENDING:
            raise serializers.ValidationError(
                "Only pending breakdowns can be rejected."
            )

        VehicleBreakdown.objects.filter(pk=instance.pk).update(
            status=VehicleBreakdown.STATUS_REJECTED,
            approval_status=VehicleBreakdown.APPROVAL_REJECTED,
            rejection_remarks=self.validated_data["rejection_remarks"],
            updated_at=now,
        )
        instance.refresh_from_db()
        # Not a real breakdown — the vehicle is back in service.
        sync_vehicle_operational_status(instance.breakdown_vehicle_id)

        from app.models.core_modules.notifications.staff_notification import StaffNotification
        from app.services.staff_notification_service import notify_staff

        # Notify the assignment's current driver — the replacement request
        # never went through, so the original vehicle/crew stands.
        assignment = instance.trip_assignment
        template = (
            (assignment.alt_staff_template or assignment.staff_template)
            if assignment
            else None
        )
        driver = template.driver if template else None
        if driver is not None:
            notify_staff(
                driver,
                StaffNotification.TYPE_VEHICLE_REPLACEMENT_REJECTED,
                title="Vehicle replacement rejected",
                body=(
                    f"Your vehicle replacement request on trip "
                    f"{assignment.unique_id} was rejected"
                    f"{': ' + instance.rejection_remarks if instance.rejection_remarks else '.'}"
                ),
                data={
                    "vehicle_breakdown_id": instance.unique_id,
                    "trip_assignment_id": assignment.unique_id,
                },
            )

        return instance


class VehicleBreakdownMarkRepairedSerializer(serializers.Serializer):
    """Used for PATCH /{id}/mark-repaired/ — the broken vehicle is fixed and
    goes back to ACTIVE. Only an approved breakdown can be closed this way;
    a pending one is closed by /verify/ or /reject/."""
    repair_remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self):
        instance = self.context["instance"]
        account = self.context.get("account")
        now = timezone.now()

        if instance.approval_status != VehicleBreakdown.APPROVAL_APPROVED:
            raise serializers.ValidationError(
                "Only approved breakdowns can be marked as repaired."
            )
        if instance.repaired_at:
            raise serializers.ValidationError("Vehicle has already been marked as repaired.")

        repaired_by = (
            Staffcreation.objects.filter(account=account)
            .values_list("staff_unique_id", flat=True)
            .first()
            if account
            else None
        )
        VehicleBreakdown.objects.filter(pk=instance.pk).update(
            repaired_at=now,
            repaired_by=repaired_by,
            repair_remarks=self.validated_data.get("repair_remarks") or None,
            updated_at=now,
        )
        instance.refresh_from_db()
        sync_vehicle_operational_status(instance.breakdown_vehicle_id)
        return instance
