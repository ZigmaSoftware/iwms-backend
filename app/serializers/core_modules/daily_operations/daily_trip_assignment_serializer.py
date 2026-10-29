from rest_framework import serializers

from app.serializers.evidence_image import absolute_image_url

from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.waste_masters.bins import Bins
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.services.daily_trip_generation import ensure_assignment_collection_points
from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.utils.related_prefetch import prefetch_related_rows, related
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

ASSIGNMENT_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "trip_plan": (TripPlan, "trip_plan_id"),
    "staff_template": (StaffTemplate, "staff_template_id"),
    "alt_staff_template": (AlternativeStaffTemplate, "alt_staff_template_id"),
    "panchayat": (Panchayat, "panchayat_id"),
    "vehicle": (VehicleCreation, "vehicle_id"),
}
PLAN_LOOKUPS = {
    "staff_template": (StaffTemplate, "staff_template_id"),
    "zone": (Zone, "zone_id"),
    "panchayat": (Panchayat, "panchayat_id"),
    "vehicle": (VehicleCreation, "vehicle_id"),
    "waste_type": (WasteType, "waste_type_id"),
}
CREW_LOOKUPS = {
    "driver": (Staffcreation, "driver_id", "staff_unique_id"),
    "operator": (Staffcreation, "operator_id", "staff_unique_id"),
}
AREA_LOOKUPS = {
    "district": (District, "district_id"),
    "city": (City, "city_id"),
}
WARD_LOOKUPS = {"zone": (Zone, "zone_id")}
STOP_LOOKUPS = {
    "collection_point": (Collection_point, "collection_point_id"),
    "bin": (Bins, "bin_id"),
    "collected_by_user": (Staffcreation, "collected_by", "staff_unique_id"),
}
BIN_LOOKUPS = {"wastetype": (WasteType, "wastetype_id")}
LOG_LOOKUPS = {
    **CREW_LOOKUPS,
    "vehicle": (VehicleCreation, "vehicle_id"),
}
RETRIP_LOOKUPS = {
    "requested_by": (Staffcreation, "requested_by_id", "staff_unique_id"),
    "reviewed_by": (Staffcreation, "reviewed_by_id", "staff_unique_id"),
}
BREAKDOWN_LOOKUPS = {
    "breakdown_vehicle": (VehicleCreation, "breakdown_vehicle_id"),
    "replacement_vehicle": (VehicleCreation, "replacement_vehicle_id"),
    "replacement_driver": (Staffcreation, "replacement_driver_id", "staff_unique_id"),
    "replacement_operator": (Staffcreation, "replacement_operator_id", "staff_unique_id"),
}


def _group(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(key(row), []).append(row)
    return grouped


def _cached(obj, name):
    """(True, value) when the list serializer prefetched `name` for `obj`."""
    cache = getattr(obj, "_dta_cache", None)
    if cache is not None and name in cache:
        return True, cache[name]
    return False, None


class DailyTripAssignmentListSerializer(serializers.ListSerializer):
    """Loads every relation, stop, log, event and sibling the row serializer
    reads in one query per table for the whole page, instead of ~50 per row."""

    def to_representation(self, data):
        from app.models.core_modules.daily_operations.daily_service_notice import DailyServiceNotice
        from app.models.core_modules.daily_operations.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
        from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
        from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
        from app.models.core_modules.daily_operations.wastecollection import WasteCollection
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import (
            TripPlanCollectionPoint,
        )
        from app.models.masters.customer_masters.customercreation import CustomerCreation

        assignments = list(data.all() if hasattr(data, "all") else data)
        if not assignments:
            return super().to_representation(assignments)
        ids = [a.unique_id for a in assignments]

        rows = prefetch_related_rows(assignments, ASSIGNMENT_LOOKUPS)
        plans = list(rows["trip_plan"].values())
        plan_rows = prefetch_related_rows(plans, PLAN_LOOKUPS)

        templates = list(rows["staff_template"].values()) + list(plan_rows["staff_template"].values())
        prefetch_related_rows(templates + list(rows["alt_staff_template"].values()), CREW_LOOKUPS)

        # Wards of every assignment and plan, kept in the query's row order as
        # `obj.wards` would return them.
        ward_ids = {wid for obj in assignments + plans for wid in obj.get_ward_ids()}
        wards = list(Ward.objects.filter(unique_id__in=ward_ids)) if ward_ids else []
        ward_rows = prefetch_related_rows(wards, WARD_LOOKUPS)
        for obj in assignments + plans:
            own = set(obj.get_ward_ids())
            obj._wards_cache = [ward for ward in wards if ward.unique_id in own]

        zones = list(plan_rows["zone"].values()) + list(ward_rows["zone"].values())
        panchayats = list(rows["panchayat"].values()) + list(plan_rows["panchayat"].values())
        prefetch_related_rows(zones + panchayats, AREA_LOOKUPS)

        plan_ids = [plan.unique_id for plan in plans]
        stop_types = {}
        for plan_id, collection_type in TripPlanCollectionPoint.objects.filter(
            trip_plan_id__in=plan_ids, is_deleted=False,
        ).values_list("trip_plan_id", "collection_type"):
            stop_types.setdefault(plan_id, set()).add(collection_type)
        for plan in plans:
            plan._stop_types_cache = stop_types.get(plan.unique_id, set())

        waste_type_ids = {str(v) for a in assignments for v in (a.waste_type_ids or []) if v}
        waste_type_ids |= {wid for a in assignments for wid in a.get_household_waste_type_ids()}
        waste_type_ids |= {str(p.waste_type_id) for p in plans if p.waste_type_id}
        waste_types = (
            list(WasteType.objects.filter(unique_id__in=waste_type_ids, is_deleted=False))
            if waste_type_ids else []
        )

        stops = list(
            DailyTripCollectionPoint.objects.filter(
                trip_assignment_id__in=ids, is_deleted=False,
            ).order_by("sequence")
        )
        stop_rows = prefetch_related_rows(stops, STOP_LOOKUPS)
        prefetch_related_rows(stop_rows["bin"].values(), BIN_LOOKUPS)
        stops_by_assignment = _group(stops, lambda stop: stop.trip_assignment_id)

        households = list(
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id__in=ids, is_deleted=False,
            ).order_by("sequence")
        )
        customer_ids = {stop.customer_id for stop in households if stop.customer_id}
        customers = {
            c.unique_id: c for c in CustomerCreation.objects.filter(unique_id__in=customer_ids)
        } if customer_ids else {}
        waste_collection_ids = {
            stop.waste_collection_id for stop in households
            if getattr(stop, "waste_collection_id", None)
        }
        waste_collections = {
            w.unique_id: w for w in WasteCollection.objects.filter(unique_id__in=waste_collection_ids)
        } if waste_collection_ids else {}
        households_by_assignment = _group(households, lambda stop: stop.trip_assignment_id)

        logs = list(DailyTripLog.objects.filter(trip_assignment_id__in=ids, is_deleted=False))
        prefetch_related_rows(logs, LOG_LOOKUPS)
        logs_by_assignment = _group(logs, lambda log: log.trip_assignment_id)

        delays_by_assignment = _group(
            TripDelayReport.objects.filter(trip_assignment_id__in=ids, is_deleted=False),
            lambda report: report.trip_assignment_id,
        )
        retrips = list(TripRetripRequest.objects.filter(assignment_id__in=ids))
        continuations = list(TripRetripRequest.objects.filter(new_assignment_id__in=ids))
        prefetch_related_rows(retrips, RETRIP_LOOKUPS)
        retrips_by_assignment = _group(retrips, lambda request: request.assignment_id)
        continuations_by_assignment = _group(continuations, lambda request: request.new_assignment_id)

        breakdowns = list(VehicleBreakdown.objects.filter(trip_assignment_id__in=ids, is_deleted=False))
        prefetch_related_rows(breakdowns, BREAKDOWN_LOOKUPS)
        breakdowns_by_assignment = _group(breakdowns, lambda bd: bd.trip_assignment_id)

        # Notices and same-day siblings are keyed on trip_plan_id; a missing
        # plan id falls back to the per-row lookup (it matches NULL there).
        planned = [a for a in assignments if a.trip_plan_id]
        planned_plan_ids = {a.trip_plan_id for a in planned}
        trip_dates = {a.trip_date for a in planned}
        notices = {}
        siblings = {}
        if planned:
            for notice in DailyServiceNotice.objects.filter(
                trip_plan_id__in=planned_plan_ids,
                service_date__in=trip_dates,
                status=DailyServiceNotice.STATUS_ACTIVE,
                is_deleted=False,
            ):
                notices.setdefault((notice.trip_plan_id, notice.service_date), notice)
            for plan_id, trip_date, unique_id in (
                DailyTripAssignment.objects.filter(
                    trip_plan_id__in=planned_plan_ids,
                    trip_date__in=trip_dates,
                    is_deleted=False,
                )
                .order_by("created_at", "unique_id")
                .values_list("trip_plan_id", "trip_date", "unique_id")
            ):
                siblings.setdefault((plan_id, trip_date), []).append(unique_id)

        for a in assignments:
            first_log = logs_by_assignment.get(a.unique_id)
            first_breakdown = breakdowns_by_assignment.get(a.unique_id)
            cache = {
                "waste_types": waste_types,
                "stops": stops_by_assignment.get(a.unique_id, []),
                "households": households_by_assignment.get(a.unique_id, []),
                "customers": customers,
                "waste_collections": waste_collections,
                "trip_log": first_log[0] if first_log else None,
                "delays": delays_by_assignment.get(a.unique_id, []),
                "retrips": retrips_by_assignment.get(a.unique_id, []),
                "continuations": continuations_by_assignment.get(a.unique_id, []),
                "breakdown": first_breakdown[0] if first_breakdown else None,
            }
            if a.trip_plan_id:
                key = (a.trip_plan_id, a.trip_date)
                cache["notice"] = notices.get(key)
                cache["siblings"] = siblings.get(key, [])
            a._dta_cache = cache

        return super().to_representation(assignments)


class DailyTripCollectionPointInlineSerializer(serializers.ModelSerializer):
    collection_point = serializers.SerializerMethodField(read_only=True)
    bin = serializers.SerializerMethodField(read_only=True)
    waste_type_name = serializers.SerializerMethodField(read_only=True)
    collected_by_staff = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyTripCollectionPoint
        fields = [
            "unique_id",
            "collection_point_id",
            "collection_point",
            "zone_id",
            "ward_id",
            "panchayat_id",
            "bin_id",
            "bin",
            "waste_type_name",
            "sequence",
            "is_collected",
            "collected_at",
            "collected_weight_kg",
            "collected_by",
            "collected_by_staff",
            "status",
            "status_reason",
        ]

    def get_collection_point(self, obj):
        cp = related(obj, "collection_point")
        if not cp:
            return None
        return {
            "unique_id": cp.unique_id,
            "cp_name": cp.cp_name,
            "latitude": cp.latitude,
            "longitude": cp.longitude,
        }

    def get_bin(self, obj):
        bin_obj = related(obj, "bin")
        if not bin_obj:
            return None
        return {
            "unique_id": bin_obj.unique_id,
            "bin_name": bin_obj.bin_name,
            "bin_capacity": bin_obj.bin_capacity,
            "bin_type": bin_obj.bin_type,
        }

    def get_collected_by_staff(self, obj):
        staff = related(obj, "collected_by_user")
        if not staff:
            return None
        return {
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }

    def get_waste_type_name(self, obj):
        bin_obj = related(obj, "bin")
        wastetype = related(bin_obj, "wastetype") if bin_obj else None
        return getattr(wastetype, "waste_type_name", None)


class DailyTripAssignmentSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    company_id_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    project_id_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    trip_plan_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=TripPlan.objects.filter(is_deleted=False, status="ACTIVE"),
        write_only=True,
    )
    staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    panchayat_id = NameOrUniqueIdField(
        slug_field="unique_id",
        name_field="panchayat_name",
        queryset=Panchayat.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    ward_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    waste_type_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=False,
    )
    household_waste_type_ids = NameOrUniqueIdField(
        slug_field="unique_id",
        name_field="waste_type_name",
        queryset=WasteType.objects.filter(is_deleted=False),
        many=True,
        required=False,
    )
    household_waste_types = serializers.SerializerMethodField(read_only=True)
    vehicle_id = NameOrUniqueIdField(
        slug_field="unique_id",
        name_field="vehicle_no",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    alt_staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=AlternativeStaffTemplate.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    trip_plan = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    alt_staff_template = serializers.SerializerMethodField(read_only=True)
    effective_staff = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    wards = serializers.SerializerMethodField(read_only=True)
    zone = serializers.SerializerMethodField(read_only=True)
    # Legacy JSON-list waste types (kept for backward compat, see waste_type_ids above).
    waste_types = serializers.SerializerMethodField(read_only=True)
    # New M2M waste types mirroring TripPlan.waste_types / TN_Iwms's
    # DailyTripAssignment.waste_types. Written via waste_types_ids.
    waste_types_ids = NameOrUniqueIdField(
        slug_field="unique_id",
        name_field="waste_type_name",
        queryset=WasteType.objects.filter(is_deleted=False),
        many=True,
        required=False,
        source="waste_types",
        write_only=True,
    )
    waste_types_detail = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    vehicle_under_breakdown = serializers.SerializerMethodField(read_only=True)
    collection_types = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    household_collection_points = serializers.SerializerMethodField(read_only=True)
    start_time = serializers.SerializerMethodField(read_only=True)
    breakdown_info = serializers.SerializerMethodField(read_only=True)
    retrip_info = serializers.SerializerMethodField(read_only=True)
    # Total time on the trip (actual_start_at -> actual_end_at, or -> now while
    # In Progress), in whole seconds — the client formats it however it needs.
    # Null until the trip has been started.
    total_trip_time_seconds = serializers.SerializerMethodField(read_only=True)
    # This assignment's 1-based position among today's assignments for the
    # same trip plan: 1 for the ordinary run, 2+ for a Re-Trip continuation
    # (and any further same-day re-trips of that continuation).
    trip_count = serializers.SerializerMethodField(read_only=True)
    trip_log_summary = serializers.SerializerMethodField(read_only=True)
    trip_events = serializers.SerializerMethodField(read_only=True)
    service_notice = serializers.SerializerMethodField(read_only=True)
    collection_points_input = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = DailyTripAssignment
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "company_id_input",
            "project_id_input",
            "trip_plan_id",
            "staff_template_id",
            "panchayat_id",
            "ward_ids",
            "waste_type_ids",
            "waste_types_ids",
            "waste_types_detail",
            "household_waste_type_ids",
            "household_waste_types",
            "vehicle_id",
            "alt_staff_template_id",
            "trip_plan",
            "staff_template",
            "alt_staff_template",
            "effective_staff",
            "panchayat",
            "wards",
            "zone",
            "waste_types",
            "vehicle",
            "vehicle_under_breakdown",
            "collection_types",
            "collection_points",
            "household_collection_points",
            "start_time",
            "collection_points_input",
            "trip_date",
            "scheduled_time",
            "actual_start_time",
            "actual_end_time",
            "actual_start_at",
            "actual_end_at",
            "trip_log_summary",
            "trip_events",
            "service_notice",
            "total_trip_time_seconds",
            "trip_count",
            "status",
            "approval_status",
            "remarks",
            "breakdown_info",
            "retrip_info",
            "created_at",
            "updated_at",
        ]
        list_serializer_class = DailyTripAssignmentListSerializer
        read_only_fields = [
            "unique_id",
            "actual_start_time",
            "actual_end_time",
            "actual_start_at",
            "actual_end_at",
            "approval_status",
            "breakdown_info",
            "retrip_info",
            "created_at",
            "updated_at",
        ]

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def get_service_notice(self, obj):
        from app.services.daily_service_notice import (
            active_notice_for_plan,
            serialize_notice,
        )

        found, notice = _cached(obj, "notice")
        if not found:
            notice = active_notice_for_plan(obj.trip_plan_id, obj.trip_date)
        return serialize_notice(notice)

    def get_trip_events(self, obj):
        from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
        from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest

        found, reports = _cached(obj, "delays")
        if not found:
            reports = TripDelayReport.objects.filter(
                trip_assignment_id=obj.unique_id, is_deleted=False
            )
        found, requests = _cached(obj, "retrips")
        if not found:
            requests = TripRetripRequest.objects.filter(assignment_id=obj.unique_id)
        found, sources = _cached(obj, "continuations")
        if not found:
            sources = TripRetripRequest.objects.filter(new_assignment_id=obj.unique_id)

        events = []
        for report in reports:
            # unique_id + image let the supervisor app open this exact
            # report (photo, acknowledge/resolve) from the trip card alerts.
            events.append({"label": "Delay: " + report.get_delay_reason_display(),
                           "detail": report.delay_remarks, "at": report.created_at,
                           "status": report.status, "kind": "delay",
                           "unique_id": report.unique_id,
                           "image": absolute_image_url(self, report.evidence_image)})
        for request in requests:
            if request.is_deleted:
                continue
            events.append({"label": "Re-Trip requested", "detail": request.reason,
                           "at": request.created_at, "status": request.status,
                           "actor": getattr(related(request, "requested_by"), "employee_name", None)})
            if request.reviewed_at:
                events.append({"label": "Re-Trip " + request.status.lower(),
                               "detail": request.review_remarks, "at": request.reviewed_at,
                               "actor": getattr(related(request, "reviewed_by"), "employee_name", None),
                               "related_trip_id": request.new_assignment_id})
        for source in sources:
            if not source.is_deleted:
                events.append({"label": "Continuation of " + str(source.assignment_id),
                               "detail": source.review_remarks, "at": source.reviewed_at,
                               "related_trip_id": source.assignment_id})
        return sorted(events, key=lambda event: str(event.get("at") or ""))

    def get_trip_log_summary(self, obj):
        from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog

        found, log = _cached(obj, "trip_log")
        if not found:
            log = DailyTripLog.objects.filter(
                trip_assignment_id=obj.unique_id, is_deleted=False,
            ).first()
        if not log:
            return None
        return {
            "unique_id": log.unique_id,
            "status": log.log_status,
            "verified_at": log.verified_at,
            "verified_by": str(log.verified_by) if log.verified_by else None,
            "bin_weight_kg": log.collected_weight_kg,
            "customer_weight_kg": log.household_collected_weight_kg,
            "driver": getattr(related(log, "driver"), "employee_name", None),
            "operator": getattr(related(log, "operator"), "employee_name", None),
            "vehicle_no": getattr(related(log, "vehicle"), "vehicle_no", None),
            "remarks": log.remarks,
        }

    def get_total_trip_time_seconds(self, obj):
        duration = obj.total_trip_time
        return int(duration.total_seconds()) if duration is not None else None

    def get_trip_count(self, obj):
        found, siblings = _cached(obj, "siblings")
        if not found:
            return obj.trip_count()
        try:
            return siblings.index(obj.unique_id) + 1
        except ValueError:
            return len(siblings) + 1

    def get_retrip_info(self, obj):
        from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest

        found, requests = _cached(obj, "retrips")
        if found:
            # Already in -created_at order (the model's ordering).
            latest = next((r for r in requests if not r.is_deleted), None)
        else:
            latest = TripRetripRequest.objects.filter(
                assignment_id=obj.unique_id, is_deleted=False
            ).order_by("-created_at").first()
        if not latest:
            return None
        return {
            "unique_id": latest.unique_id,
            "status": latest.status,
            "new_assignment_id": latest.new_assignment_id,
            "expires_at": latest.expires_at,
        }

    def get_breakdown_info(self, obj):
        from app.models.core_modules.daily_operations.vehicle_breakdown import (
            VehicleBreakdown,
            VehicleBreakdownPhoto,
        )

        found, bd = _cached(obj, "breakdown")
        if not found:
            bd = VehicleBreakdown.objects.filter(
                trip_assignment_id=obj.unique_id, is_deleted=False,
            ).first()
        if not bd:
            return None
        return {
            "unique_id": bd.unique_id,
            "status": bd.status,
            "approval_status": bd.approval_status,
            "breakdown_reason": bd.breakdown_reason,
            "breakdown_time": str(bd.breakdown_time) if bd.breakdown_time else None,
            "breakdown_location": bd.breakdown_location,
            "breakdown_vehicle_no": getattr(related(bd, "breakdown_vehicle"), "vehicle_no", None),
            "replacement_vehicle_no": getattr(related(bd, "replacement_vehicle"), "vehicle_no", None),
            "replacement_driver": getattr(related(bd, "replacement_driver"), "employee_name", None),
            "replacement_operator": getattr(related(bd, "replacement_operator"), "employee_name", None),
            "new_assignment_id": bd.new_assignment,
            "photos": [
                url
                for photo in VehicleBreakdownPhoto.objects.filter(breakdown_id=bd.unique_id)
                if (url := absolute_image_url(self, photo.photo))
            ],
        }

    def get_trip_plan(self, obj):
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
        plan = related(obj, "trip_plan")
        if not plan:
            return None
        stop_types = self._plan_stop_types(plan)
        staff_template = related(plan, "staff_template")
        return {
            "unique_id": plan.unique_id,
            "display_code": plan.display_code,
            "staff_template_id": getattr(staff_template, "unique_id", None),
            "staff_template": self._staff_template_payload(staff_template),
            "scheduled_time": plan.scheduled_time,
            "zone": self._zone_payload(related(plan, "zone")),
            "panchayat": self._panchayat_payload(related(plan, "panchayat")),
            "wards": [self._ward_payload(w) for w in self._wards(plan)],
            "vehicle_no": getattr(related(plan, "vehicle"), "vehicle_no", None),
            "waste_type_name": getattr(related(plan, "waste_type"), "waste_type_name", None),
            "waste_type_ids": plan.waste_type_ids or ([plan.waste_type_id] if plan.waste_type_id else []),
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stop_types,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stop_types,
        }

    @staticmethod
    def _plan_stop_types(plan):
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint

        cached = getattr(plan, "_stop_types_cache", None)
        if cached is not None:
            return cached
        return list(
            TripPlanCollectionPoint.objects.filter(
                trip_plan_id=plan.unique_id, is_deleted=False,
            ).values_list("collection_type", flat=True)
        )

    @staticmethod
    def _wards(obj):
        cached = getattr(obj, "_wards_cache", None)
        return cached if cached is not None else obj.wards

    @staticmethod
    def _first_ward(obj):
        # Same row as `obj.wards.first()` (Ward's pk is unique_id).
        cached = getattr(obj, "_wards_cache", None)
        if cached is None:
            return obj.wards.first()
        return min(cached, key=lambda ward: ward.unique_id, default=None)

    def get_staff_template(self, obj):
        return self._staff_template_payload(related(obj, "staff_template"))

    def _staff_template_payload(self, staff_template):
        if not staff_template:
            return None
        return {
            "unique_id": staff_template.unique_id,
            "display_code": staff_template.display_code,
            "driver": getattr(related(staff_template, "driver"), "employee_name", None),
            "operator": getattr(related(staff_template, "operator"), "employee_name", None),
        }

    def get_alt_staff_template(self, obj):
        alt = related(obj, "alt_staff_template")
        if not alt:
            return None
        return {
            "unique_id": alt.unique_id,
            "display_code": alt.display_code,
            "driver": getattr(related(alt, "driver"), "employee_name", None),
            "operator": getattr(related(alt, "operator"), "employee_name", None),
            "from_date": str(alt.from_date),
            "to_date": str(alt.to_date),
        }

    def get_effective_staff(self, obj):
        alt = related(obj, "alt_staff_template")
        if alt:
            return {
                "source": "alternative",
                "unique_id": alt.unique_id,
                "display_code": alt.display_code,
                "driver": getattr(related(alt, "driver"), "employee_name", None),
                "operator": getattr(related(alt, "operator"), "employee_name", None),
                "from_date": str(alt.from_date),
                "to_date": str(alt.to_date),
            }
        st = related(obj, "staff_template")
        if not st:
            return None
        return {
            "source": "base",
            "unique_id": st.unique_id,
            "display_code": st.display_code,
            "driver": getattr(related(st, "driver"), "employee_name", None),
            "operator": getattr(related(st, "operator"), "employee_name", None),
        }

    def get_panchayat(self, obj):
        return self._panchayat_payload(related(obj, "panchayat"))

    def get_wards(self, obj):
        return [self._ward_payload(w) for w in self._wards(obj)]

    def get_zone(self, obj):
        plan = related(obj, "trip_plan")
        plan_zone = related(plan, "zone") if plan else None
        if plan_zone:
            return self._zone_payload(plan_zone)
        # Fall back to zone from this assignment's own wards
        first_ward = self._first_ward(obj)
        if first_ward:
            return self._zone_payload(related(first_ward, "zone"))
        # Fall back to zone from the trip plan's wards
        if plan:
            first_plan_ward = self._first_ward(plan)
            if first_plan_ward:
                return self._zone_payload(related(first_plan_ward, "zone"))
        return None

    def _panchayat_payload(self, panchayat):
        if not panchayat:
            return None
        district = related(panchayat, "district")
        city = related(panchayat, "city")
        return {
            "unique_id": panchayat.unique_id,
            "panchayat_name": panchayat.panchayat_name,
            "district_id": getattr(district, "unique_id", None),
            "district_name": getattr(district, "name", None),
            "city_id": getattr(city, "unique_id", None),
            "city_name": getattr(city, "name", None),
        }

    def _ward_payload(self, ward):
        if not ward:
            return None
        zone = related(ward, "zone")
        return {
            "unique_id": ward.unique_id,
            "ward_name": ward.ward_name,
            "zone_id": getattr(zone, "unique_id", None),
            "zone_name": getattr(zone, "zone_name", None),
        }

    def _zone_payload(self, zone):
        if not zone:
            return None
        district = related(zone, "district")
        city = related(zone, "city")
        return {
            "unique_id": zone.unique_id,
            "zone_name": zone.zone_name,
            "district_id": getattr(district, "unique_id", None),
            "district_name": getattr(district, "name", None),
            "city_id": getattr(city, "unique_id", None),
            "city_name": getattr(city, "name", None),
        }

    def get_waste_types(self, obj):
        ids = obj.waste_type_ids or []
        by_id = {item.unique_id: item for item in self._waste_types(obj, ids)}
        return [
            {"unique_id": waste_type_id, "waste_type_name": getattr(by_id[waste_type_id], "waste_type_name", None)}
            for waste_type_id in ids
            if waste_type_id in by_id
        ]

    def get_waste_types_detail(self, obj):
        """Every waste type on this trip, from the JSON list and the M2M alike.

        Trip creation writes `waste_type_ids`, other flows fill the `waste_types`
        M2M; reading only the M2M reported no waste types at all for trips
        created through the form.
        """
        from app.viewsets.operator_mobile.helpers import _assignment_waste_type_ids

        found, _ = _cached(obj, "waste_types")
        if found:
            # _assignment_waste_type_ids, reading the prefetched plan.
            ids = {str(v) for v in (obj.waste_type_ids or []) if v}
            plan = related(obj, "trip_plan")
            if plan and plan.waste_type_id:
                ids.add(str(plan.waste_type_id))
            ids = {i for i in ids if i}
        else:
            ids = _assignment_waste_type_ids(obj)
        if not ids:
            return []
        ordered = [str(v) for v in (obj.waste_type_ids or []) if str(v) in ids]
        ordered += sorted(ids - set(ordered))
        by_id = {wt.unique_id: wt for wt in self._waste_types(obj, ids)}
        return [
            {
                "unique_id": waste_type_id,
                "waste_type_name": getattr(by_id[waste_type_id], "waste_type_name", None),
            }
            for waste_type_id in ordered
            if waste_type_id in by_id
        ]

    @staticmethod
    def _waste_types(obj, ids):
        """Non-deleted waste types among `ids`, in the query's row order."""
        found, waste_types = _cached(obj, "waste_types")
        if not found:
            return WasteType.objects.filter(unique_id__in=ids, is_deleted=False)
        ids = set(ids)
        return [wt for wt in waste_types if wt.unique_id in ids]

    def _vehicle(self, obj):
        # `obj.vehicle` queries on every access; both fields below need it.
        if not hasattr(obj, "_vehicle_row"):
            obj._vehicle_row = related(obj, "vehicle")
        return obj._vehicle_row

    def get_vehicle(self, obj):
        vehicle = self._vehicle(obj)
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "operational_status": vehicle.operational_status,
        }

    def get_vehicle_under_breakdown(self, obj):
        """Not started yet and its vehicle is broken down — it cannot start
        until it is moved to another vehicle or the vehicle is repaired.
        Same rule as DailyTripAssignment.blocked_by_vehicle_breakdown()."""
        vehicle = self._vehicle(obj)
        return bool(
            vehicle
            and not obj.actual_start_at
            and obj.status == DailyTripAssignment.STATUS_SCHEDULED
            and vehicle.operational_status == VehicleCreation.OperationalStatus.BREAKDOWN
        )

    def get_household_waste_types(self, obj):
        ids = obj.get_household_waste_type_ids()
        waste_types = self._waste_types(obj, ids)
        return [
            {"unique_id": wt.unique_id, "waste_type_name": getattr(wt, "waste_type_name", None)}
            for wt in waste_types
        ]

    def get_collection_types(self, obj):
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
        plan = related(obj, "trip_plan")
        if not plan:
            return {"has_bin": False, "has_household": False}
        stops = self._plan_stop_types(plan)
        return {
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stops,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stops,
        }

    def get_collection_points(self, obj):
        found, stops = _cached(obj, "stops")
        if not found:
            stops = obj.trip_collection_points.filter(is_deleted=False).order_by("sequence")
        return DailyTripCollectionPointInlineSerializer(stops, many=True).data

    def get_household_collection_points(self, obj):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        from app.models.core_modules.daily_operations.wastecollection import WasteCollection

        found, stops = _cached(obj, "households")
        if found:
            customers_by_id = obj._dta_cache["customers"]
            waste_collections_by_id = obj._dta_cache["waste_collections"]
        else:
            stops = obj.trip_household_collections.filter(is_deleted=False).order_by("sequence")
            customer_ids = {stop.customer_id for stop in stops if stop.customer_id}
            customers_by_id = {
                c.unique_id: c
                for c in CustomerCreation.objects.filter(unique_id__in=customer_ids)
            }
            waste_collection_ids = {stop.waste_collection_id for stop in stops if getattr(stop, "waste_collection_id", None)}
            waste_collections_by_id = {
                w.unique_id: w
                for w in WasteCollection.objects.filter(unique_id__in=waste_collection_ids)
            }
        result = []
        for stop in stops:
            customer = customers_by_id.get(stop.customer_id)
            waste_collection = waste_collections_by_id.get(getattr(stop, "waste_collection_id", None))
            result.append({
                "unique_id": stop.unique_id,
                "customer_id": stop.customer_id,
                "customer": {
                    "unique_id": getattr(customer, "unique_id", None),
                    "customer_name": getattr(customer, "customer_name", None),
                    "building_no": getattr(customer, "building_no", None),
                    "street": getattr(customer, "street", None),
                } if customer else None,
                "collection_type": stop.collection_type,
                "sequence": stop.sequence,
                "is_collected": stop.is_collected,
                "collected_at": str(stop.collected_at) if stop.collected_at else None,
                "collected_weight_kg": str(stop.collected_weight_kg) if stop.collected_weight_kg is not None else None,
                "wet_waste": getattr(waste_collection, "wet_waste", None),
                "dry_waste": getattr(waste_collection, "dry_waste", None),
                "mixed_waste": getattr(waste_collection, "mixed_waste", None),
                "sanitary_waste": getattr(waste_collection, "sanitary_waste", None),
                "status": stop.status,
                "status_reason": stop.status_reason,
                "customer_available_at": (
                    stop.customer_available_at.isoformat() if stop.customer_available_at else None
                ),
                "customer_available_note": stop.customer_available_note,
            })
        return result

    def get_start_time(self, obj):
        return str(obj.scheduled_time) if obj.scheduled_time else None

    def _resolve_unique_id(self, model, value, field="unique_id"):
        """The id string itself, once confirmed to exist — raises like
        `.get()` did previously if `value` doesn't resolve."""
        if not value:
            return None
        model.objects.get(**{field: value})
        return value

    def _sync_collection_points(self, assignment, points):
        if points is None:
            ensure_assignment_collection_points(
                assignment,
                created_by=getattr(self.context.get("request"), "user", None),
            )
            return

        for item in points:
            unique_id = item.get("unique_id")
            instance = None
            if unique_id:
                instance = DailyTripCollectionPoint.objects.filter(
                    unique_id=unique_id,
                    trip_assignment_id=assignment.unique_id,
                    is_deleted=False,
                ).first()
            if not instance:
                collection_point_id = item.get("collection_point_id")
                if not collection_point_id:
                    continue
                instance = DailyTripCollectionPoint(
                    trip_assignment_id=assignment.unique_id,
                    collection_point_id=self._resolve_unique_id(
                        Collection_point,
                        collection_point_id,
                    ),
                )

            for field in [
                "sequence",
                "is_collected",
                "collected_at",
                "collected_weight_kg",
                "status",
            ]:
                if field in item:
                    setattr(instance, field, item.get(field))

            if "collection_point_id" in item and item.get("collection_point_id"):
                instance.collection_point_id = self._resolve_unique_id(
                    Collection_point,
                    item.get("collection_point_id"),
                )
            if "bin_id" in item and item.get("bin_id"):
                instance.bin_id = self._resolve_unique_id(Bins, item.get("bin_id"))
            if "collected_by" in item:
                instance.collected_by = self._resolve_unique_id(
                    Staffcreation,
                    item.get("collected_by"),
                    field="staff_unique_id",
                )
            if item.get("is_collected") or item.get("collected_at"):
                instance.is_collected = True
                instance.status = DailyTripCollectionPoint.STATUS_COLLECTED
            instance.save()

        ensure_assignment_collection_points(
            assignment,
            created_by=getattr(self.context.get("request"), "user", None),
        )

    def _sync_wards(self, assignment, ward_ids):
        if ward_ids is None:
            return
        valid_ids = list(
            Ward.objects.filter(unique_id__in=ward_ids, is_deleted=False).values_list("unique_id", flat=True)
        )
        assignment.ward_ids = ",".join(valid_ids)
        assignment.save(update_fields=["ward_ids"])

    @staticmethod
    def _pop_waste_types(validated_data):
        # waste_types_ids (source="waste_types") resolves to WasteType
        # instances, but the model only persists waste types via the
        # waste_type_ids JSONField — there is no `waste_types` model field.
        waste_types = validated_data.pop("waste_types", None)
        if waste_types is not None:
            validated_data["waste_type_ids"] = [wt.unique_id for wt in waste_types]

    @staticmethod
    def _normalize_related_ids(validated_data):
        """panchayat_id/vehicle_id/household_waste_type_ids all resolve to
        model instances via NameOrUniqueIdField (it writes as unique_id but
        reads as an object), while the model fields they map onto are plain
        CharField/TextField id columns — convert before the model save."""
        panchayat = validated_data.get("panchayat_id")
        if hasattr(panchayat, "unique_id"):
            validated_data["panchayat_id"] = panchayat.unique_id
        vehicle = validated_data.get("vehicle_id")
        if hasattr(vehicle, "unique_id"):
            validated_data["vehicle_id"] = vehicle.unique_id
        household_waste_types = validated_data.pop("household_waste_type_ids", None)
        if household_waste_types is not None:
            validated_data["household_waste_type_ids"] = ",".join(
                wt.unique_id for wt in household_waste_types
            )

    def create(self, validated_data):
        collection_points = validated_data.pop("collection_points_input", None)
        ward_ids = validated_data.pop("ward_ids", None)
        self._pop_waste_types(validated_data)
        self._normalize_related_ids(validated_data)
        assignment = super().create(validated_data)
        self._sync_wards(assignment, ward_ids)
        sync_daily_assignment_stops_from_plan(assignment)
        self._sync_collection_points(assignment, collection_points)
        return assignment

    def update(self, instance, validated_data):
        collection_points = validated_data.pop("collection_points_input", None)
        ward_ids = validated_data.pop("ward_ids", None)
        self._pop_waste_types(validated_data)
        self._normalize_related_ids(validated_data)
        assignment = super().update(instance, validated_data)
        self._sync_wards(assignment, ward_ids)
        sync_daily_assignment_stops_from_plan(assignment)
        self._sync_collection_points(assignment, collection_points)
        return assignment

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        instance = getattr(self, "instance", None)
        trip_plan_id = attrs.get("trip_plan_id", getattr(instance, "trip_plan_id", None))
        trip_plan = TripPlan.objects.filter(unique_id=trip_plan_id).first() if trip_plan_id else None
        trip_date = attrs.get("trip_date", getattr(instance, "trip_date", None))
        scheduled_time = attrs.get(
            "scheduled_time",
            getattr(instance, "scheduled_time", None),
        )

        if trip_plan:
            attrs.setdefault("staff_template_id", trip_plan.staff_template_id)
            if "vehicle_id" not in attrs:
                from app.services.vehicle_substitution import vehicle_for_plan

                # The plan's breakdown replacement vehicle, if it has one;
                # otherwise its own (refused below when under breakdown).
                substitute_id, _ = (
                    vehicle_for_plan(trip_plan, trip_date) if trip_date else (None, None)
                )
                attrs["vehicle_id"] = substitute_id or trip_plan.vehicle
            attrs.setdefault("panchayat_id", trip_plan.panchayat)
            if "ward_ids" not in attrs:
                plan_ward_ids = trip_plan.get_ward_ids()
                if plan_ward_ids:
                    attrs["ward_ids"] = plan_ward_ids
            if "waste_types" not in attrs and not (instance and instance.waste_type_ids):
                plan_waste_type_ids = trip_plan.waste_type_ids or (
                    [trip_plan.waste_type_id] if trip_plan.waste_type_id else []
                )
                if plan_waste_type_ids:
                    attrs["waste_type_ids"] = plan_waste_type_ids
            attrs.setdefault("scheduled_time", trip_plan.scheduled_time)
            scheduled_time = attrs.get("scheduled_time", scheduled_time)

        waste_type_ids = attrs.get("waste_type_ids")
        if waste_type_ids is not None:
            normalized_waste_type_ids = [
                str(waste_type_id)
                for waste_type_id in waste_type_ids
                if str(waste_type_id)
            ]
            if len(normalized_waste_type_ids) != len(set(normalized_waste_type_ids)):
                raise serializers.ValidationError(
                    {"waste_type_ids": "Waste types must be unique."}
                )
            valid_count = WasteType.objects.filter(
                unique_id__in=normalized_waste_type_ids,
                is_deleted=False,
            ).count()
            if valid_count != len(normalized_waste_type_ids):
                raise serializers.ValidationError(
                    {"waste_type_ids": "Invalid waste type selected."}
                )
            attrs["waste_type_ids"] = normalized_waste_type_ids
        elif trip_plan and not getattr(instance, "waste_type_ids", None):
            plan_waste_type_ids = [
                waste_type_id
                for waste_type_id in (trip_plan.waste_type_ids or [trip_plan.waste_type_id])
                if waste_type_id
            ]
            attrs.setdefault(
                "waste_type_ids",
                plan_waste_type_ids,
            )

        ward_ids = attrs.get("ward_ids")
        existing_wards = bool(instance and instance.get_ward_ids()) if instance else False
        if not ward_ids and not existing_wards:
            raise serializers.ValidationError(
                {"ward_ids": "At least one ward is required for the daily trip assignment."}
            )

        if trip_plan and trip_date and scheduled_time:
            conflict_qs = DailyTripAssignment.objects.filter(
                trip_plan_id=trip_plan.unique_id,
                trip_date=trip_date,
                is_deleted=False,
            ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            if instance:
                conflict_qs = conflict_qs.exclude(pk=instance.pk)
            if conflict_qs.exists():
                raise serializers.ValidationError(
                    "Trip plan already assigned for this date and time."
                )

        staff_template = attrs.get(
            "staff_template_id",
            getattr(instance, "staff_template_id", None),
        )
        vehicle = attrs.get(
            "vehicle_id",
            getattr(instance, "vehicle_id", None),
        )

        vehicle_id = vehicle.unique_id if hasattr(vehicle, "unique_id") else vehicle
        # Only on create or a vehicle change — the trip the vehicle broke down
        # on must stay editable so it can be closed out.
        if (
            vehicle_id
            and (instance is None or vehicle_id != instance.vehicle_id)
            and VehicleCreation.objects.filter(
                unique_id=vehicle_id,
                operational_status=VehicleCreation.OperationalStatus.BREAKDOWN,
            ).exists()
        ):
            raise serializers.ValidationError(
                {
                    "vehicle_id": (
                        "This vehicle is under breakdown. Set a replacement "
                        "vehicle on the trip plan, or mark it repaired first."
                    )
                }
            )

        if trip_date and (staff_template or vehicle):
            busy_qs = DailyTripAssignment.objects.filter(
                trip_date=trip_date,
                is_deleted=False,
            ).exclude(
                status__in=[
                    DailyTripAssignment.STATUS_CANCELLED,
                    DailyTripAssignment.STATUS_COMPLETED,
                ]
            )
            if instance:
                busy_qs = busy_qs.exclude(pk=instance.pk)

            if staff_template and busy_qs.filter(staff_template_id=staff_template).exists():
                raise serializers.ValidationError(
                    {
                        "staff_template_id": (
                            "This staff template is already assigned to another "
                            "trip today. Complete or unassign that trip first."
                        )
                    }
                )
            vehicle_id = vehicle.unique_id if hasattr(vehicle, "unique_id") else vehicle
            if vehicle_id and busy_qs.filter(vehicle_id=vehicle_id).exists():
                raise serializers.ValidationError(
                    {
                        "vehicle_id": (
                            "This vehicle is already assigned to another trip "
                            "today. Complete or unassign that trip first."
                        )
                    }
                )
        if staff_template and trip_date and "alt_staff_template_id" not in attrs:
            alt_template = AlternativeStaffTemplate.objects.filter(
                staff_template_id=staff_template,
                from_date__lte=trip_date,
                to_date__gte=trip_date,
            ).first()
            if alt_template:
                attrs["alt_staff_template_id"] = alt_template.unique_id

        return attrs


class DailyTripAssignmentStatusSerializer(serializers.Serializer):
    VALID_TRANSITIONS = {
        DailyTripAssignment.STATUS_SCHEDULED: [DailyTripAssignment.STATUS_IN_PROGRESS],
        DailyTripAssignment.STATUS_IN_PROGRESS: [DailyTripAssignment.STATUS_COMPLETED],
    }

    status = serializers.ChoiceField(choices=DailyTripAssignment.STATUS_CHOICES)

    def validate_status(self, value):
        instance = self.context.get("instance")
        if not instance:
            return value

        current = instance.status
        new = value
        if new == DailyTripAssignment.STATUS_CANCELLED:
            return value

        allowed_next = self.VALID_TRANSITIONS.get(current, [])
        if new not in allowed_next:
            raise serializers.ValidationError(
                f"Cannot transition from '{current}' to '{new}'. "
                f"Allowed: {allowed_next or ['Cancelled']}."
            )

        if (
            new == DailyTripAssignment.STATUS_IN_PROGRESS
            and instance.approval_status != DailyTripAssignment.APPROVAL_APPROVED
        ):
            raise serializers.ValidationError(
                "Trip must be Approved before it can be started."
            )

        return value


class DailyTripAssignmentApprovalSerializer(serializers.Serializer):
    approval_status = serializers.ChoiceField(
        choices=DailyTripAssignment.APPROVAL_CHOICES
    )

    def validate_approval_status(self, value):
        instance = self.context.get("instance")
        if not instance:
            return value

        current = instance.approval_status
        if current != DailyTripAssignment.APPROVAL_PENDING:
            raise serializers.ValidationError(
                f"Only Pending assignments can be approved or rejected. "
                f"Current status: '{current}'."
            )

        if value not in (
            DailyTripAssignment.APPROVAL_APPROVED,
            DailyTripAssignment.APPROVAL_REJECTED,
        ):
            raise serializers.ValidationError(
                "approval_status must be 'Approved' or 'Rejected'."
            )

        return value
