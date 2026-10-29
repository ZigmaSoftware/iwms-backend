from django.utils import timezone
from rest_framework import serializers

from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.serializers.evidence_image import absolute_image_url
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.utils.related_prefetch import cached_related, prefetch_related_rows, related
from app.utils.waste_images import capture_images_for_customers
from app.utils.waste_type_breakdown import bulk_waste_type_rows_for_trip_assignments


def _log_lookups():
    from app.models.core_modules.daily_operations.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )
    from app.models.core_modules.daily_operations.wastecollection import WasteCollection
    from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
    from app.models.core_modules.schedule_setup.collection_point import Collection_point
    from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
    from app.models.core_modules.schedule_setup.trip_plan import TripPlan
    from app.models.masters.city import City
    from app.models.masters.district import District
    from app.models.masters.zone import Zone
    from app.models.superadmin_masters.company import Company
    from app.models.superadmin_masters.project import Project
    from app.models.masters.customer_masters.customercreation import CustomerCreation
    from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType

    staff = (Staffcreation, "driver_id", "staff_unique_id")
    return {
        "log": {
            "company": (Company, "company_id"),
            "project": (Project, "project_id"),
            "trip_assignment": (DailyTripAssignment, "trip_assignment_id"),
            "staff_template": (StaffTemplate, "staff_template_id"),
            "alt_staff_template": (AlternativeStaffTemplate, "alt_staff_template_id"),
            "driver": staff,
            "operator": (Staffcreation, "operator_id", "staff_unique_id"),
            "vehicle": (VehicleCreation, "vehicle_id"),
            "collection_point": (Collection_point, "collection_point_id"),
            "waste_type": (WasteType, "waste_type_id"),
        },
        "assignment": {
            "trip_plan": (TripPlan, "trip_plan_id"),
            "staff_template": (StaffTemplate, "staff_template_id"),
            "alt_staff_template": (AlternativeStaffTemplate, "alt_staff_template_id"),
        },
        "plan": {
            "district": (District, "district_id"),
            "city": (City, "city_id"),
            "zone": (Zone, "zone_id"),
        },
        "template": {
            "driver": staff,
            "operator": (Staffcreation, "operator_id", "staff_unique_id"),
        },
        "household": {
            "customer": (CustomerCreation, "customer_id"),
            "waste_collection": (WasteCollection, "waste_collection_id"),
        },
        "stop": {
            "collection_point": (Collection_point, "collection_point_id"),
        },
        "household_model": DailyTripHouseholdCollection,
    }


def _attach_stops(assignments):
    """Load the bin and household stops of `assignments` (one query each for
    the whole batch, plus their customers / waste collections / collection
    points) and keep them on each assignment for every field that reads them."""
    from app.models.core_modules.daily_operations.daily_trip_collection_point import (
        DailyTripCollectionPoint,
    )

    lookups = _log_lookups()
    assignments = [a for a in assignments if a is not None and "_households_cache" not in a.__dict__]
    if not assignments:
        return
    ids = [a.unique_id for a in assignments]

    households = list(
        lookups["household_model"].objects.filter(trip_assignment_id__in=ids, is_deleted=False)
    )
    prefetch_related_rows(households, lookups["household"])
    stops = list(
        DailyTripCollectionPoint.objects.filter(trip_assignment_id__in=ids, is_deleted=False)
        .order_by("sequence")
    )
    prefetch_related_rows(stops, lookups["stop"])

    for assignment in assignments:
        assignment._households_cache = [h for h in households if h.trip_assignment_id == assignment.unique_id]
        assignment._bin_stops_cache = [s for s in stops if s.trip_assignment_id == assignment.unique_id]


class DailyTripLogListSerializer(serializers.ListSerializer):
    """Resolves the relations every log reads — assignment, plan, templates,
    staff, stops and households — in one query per table for the page."""

    def to_representation(self, data):
        logs = list(data.all() if hasattr(data, "all") else data)
        lookups = _log_lookups()

        rows = prefetch_related_rows(logs, lookups["log"])
        assignments = list(rows["trip_assignment"].values())
        assignment_rows = prefetch_related_rows(assignments, lookups["assignment"])
        prefetch_related_rows(assignment_rows["trip_plan"].values(), lookups["plan"])
        prefetch_related_rows(
            [*rows["staff_template"].values(), *rows["alt_staff_template"].values(),
             *assignment_rows["staff_template"].values(), *assignment_rows["alt_staff_template"].values()],
            lookups["template"],
        )
        _attach_stops(assignments)

        from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
        from app.viewsets.operator_mobile.helpers import _assignment_waste_type_ids

        # The breakdown helper is already bulk; call it once for the page.
        breakdown = bulk_waste_type_rows_for_trip_assignments(
            [a.unique_id for a in assignments], source="all",
        )
        waste_type_ids = {}
        for assignment in assignments:
            assignment._waste_breakdown_cache = [
                row for row in breakdown if row["trip_assignment_id"] == assignment.unique_id
            ]
            waste_type_ids[assignment.unique_id] = _assignment_waste_type_ids(
                assignment, trip_plan=cached_related(assignment, "trip_plan"),
            )
        all_ids = set().union(*waste_type_ids.values()) if waste_type_ids else set()
        self.child._waste_types_by_id = {
            wt.unique_id: wt
            for wt in WasteType.objects.filter(unique_id__in=all_ids, is_deleted=False)
        } if all_ids else {}

        return super().to_representation(logs)


class DailyTripLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    # Trip assignments have no separate "name" — they're identified by their
    # unique_id/display code — so this stays ID-based (unlike name-driven
    # master lookups below).
    trip_assignment_id = UniqueIdOrPkField(
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
        write_only=True,
    )
    bin_ids = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Comma-separated list of bin unique_ids",
    )
    extra_operator_ids = NameOrUniqueIdField(
        queryset=Staffcreation.objects.filter(is_deleted=False),
        many=True,
        required=False,
    )

    trip_assignment = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    zone = serializers.SerializerMethodField(read_only=True)
    ward = serializers.SerializerMethodField(read_only=True)
    wards_detail = serializers.SerializerMethodField(read_only=True)
    location = serializers.SerializerMethodField(read_only=True)
    collection_point = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    waste_type = serializers.SerializerMethodField(read_only=True)
    waste_types_detail = serializers.SerializerMethodField(read_only=True)
    driver = serializers.SerializerMethodField(read_only=True)
    operator = serializers.SerializerMethodField(read_only=True)
    extra_operators = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    bins = serializers.SerializerMethodField(read_only=True)
    verified_by_name = serializers.SerializerMethodField(read_only=True)
    collection_status = serializers.SerializerMethodField(read_only=True)
    household_collections = serializers.SerializerMethodField(read_only=True)
    waste_type_breakdown = serializers.SerializerMethodField(read_only=True)
    capture_images = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.CharField(source="created_by_id", read_only=True)

    class Meta:
        model = DailyTripLog
        fields = [
            "unique_id",
            "trip_assignment_id",
            "trip_assignment",
            "staff_template_id",
            "staff_template",
            "alt_staff_template_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "panchayat_id",
            "panchayat",
            "zone",
            "ward",
            "wards_detail",
            "location",
            "collection_point_id",
            "collection_point",
            "collection_points",
            "waste_type_id",
            "waste_type",
            "waste_types_detail",
            "trip_date",
            "actual_start_time",
            "actual_end_time",
            "driver_id",
            "driver",
            "operator_id",
            "operator",
            "extra_operator_ids",
            "extra_operators",
            "collected_weight_kg",
            "household_collected_weight_kg",
            "vehicle_id",
            "vehicle",
            "bin_ids",
            "bins",
            "remarks",
            "log_status",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "collection_status",
            "household_collections",
            "waste_type_breakdown",
            "capture_images",
            "created_by",
            "created_at",
            "updated_at",
        ]
        list_serializer_class = DailyTripLogListSerializer
        read_only_fields = [
            "unique_id",
            "staff_template_id",
            "alt_staff_template_id",
            "company_id",
            "project_id",
            "panchayat_id",
            "collection_point_id",
            "waste_type_id",
            "trip_date",
            "driver_id",
            "operator_id",
            "vehicle_id",
            "collected_weight_kg",
            "verified_by",
            "verified_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    # --------------------------------------------------
    # Shared lookups — each field below reads the same assignment, plan,
    # stops and wards, so they are resolved once per log (and once per page
    # for lists, see DailyTripLogListSerializer) instead of once per field.
    # --------------------------------------------------
    def _assignment(self, obj):
        return cached_related(obj, "trip_assignment")

    def _trip_plan(self, assignment):
        return cached_related(assignment, "trip_plan") if assignment else None

    def _households(self, assignment):
        _attach_stops([assignment])
        return assignment._households_cache

    def _bin_stops(self, assignment):
        _attach_stops([assignment])
        return assignment._bin_stops_cache

    def _wards(self, assignment):
        cached = assignment.__dict__.get("_wards_cache")
        if cached is None:
            from app.models.masters.ward import Ward
            cached = list(Ward.objects.filter(unique_id__in=assignment.get_ward_ids()))
            assignment._wards_cache = cached
        return cached

    def _lookup(self, model, unique_id):
        """One query per distinct row for the whole response."""
        memo = self.root.__dict__.setdefault("_lookup_memo", {})
        key = (model, unique_id)
        if key not in memo:
            memo[key] = model.objects.filter(unique_id=unique_id).first()
        return memo[key]

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def get_trip_assignment(self, obj):
        assignment = self._assignment(obj)
        if not assignment:
            return None
        trip_plan = self._trip_plan(assignment)
        zone = related(trip_plan, "zone") if trip_plan else None
        return {
            "unique_id": assignment.unique_id,
            "status": assignment.status,
            "approval_status": assignment.approval_status,
            "trip_date": str(assignment.trip_date),
            "scheduled_time": str(assignment.scheduled_time),
            "display_code": getattr(trip_plan, "display_code", assignment.unique_id),
            "zone": (
                {"unique_id": zone.unique_id, "zone_name": zone.zone_name}
                if zone else None
            ),
        }

    def get_wards_detail(self, obj):
        assignment = self._assignment(obj)
        if not assignment:
            return []
        return [
            {"unique_id": ward.unique_id, "ward_name": ward.ward_name}
            for ward in self._wards(assignment)
        ]

    def get_staff_template(self, obj):
        # Fall back to trip assignment's templates for records created before the migration
        assignment = self._assignment(obj)
        template = related(obj, "staff_template") or (
            cached_related(assignment, "staff_template") if assignment else None
        )
        alt = related(obj, "alt_staff_template") or (
            cached_related(assignment, "alt_staff_template") if assignment else None
        )
        if not template and not alt:
            return None
        result = {
            "is_alt": alt is not None,
            "effective_display_code": (alt or template).display_code,
        }
        if template:
            result["base"] = {
                "unique_id": template.unique_id,
                "display_code": template.display_code,
                "driver": self._staff_dict(related(template, "driver")),
                "operator": self._staff_dict(related(template, "operator")),
            }
        if alt:
            result["alt"] = {
                "unique_id": alt.unique_id,
                "display_code": alt.display_code,
                "driver": self._staff_dict(related(alt, "driver")),
                "operator": self._staff_dict(related(alt, "operator")),
            }
        return result

    def get_collection_points(self, obj):
        from django.db.models import Sum
        from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent

        assignment = self._assignment(obj)
        if not assignment:
            return []
        from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType

        cps = self._bin_stops(assignment)
        breakdown_by_stop = {}
        evidence_by_stop = {}
        stop_ids = [tcp.unique_id for tcp in cps]
        if stop_ids:
            rows = (
                BinCollectionEvent.objects.filter(
                    trip_collection_point_id__in=stop_ids, is_deleted=False,
                )
                .values("trip_collection_point_id", "waste_type_id")
                .annotate(total_weight=Sum("collected_weight_kg"))
            )
            waste_type_names = dict(
                WasteType.objects.filter(
                    unique_id__in=[row["waste_type_id"] for row in rows if row["waste_type_id"]]
                ).values_list("unique_id", "waste_type_name")
            )
            for row in rows:
                if not row["total_weight"]:
                    continue
                breakdown_by_stop.setdefault(row["trip_collection_point_id"], []).append({
                    "waste_type_name": waste_type_names.get(row["waste_type_id"]),
                    "collected_weight_kg": str(row["total_weight"]),
                })
            evidence_events = (
                BinCollectionEvent.objects.filter(
                    trip_collection_point_id__in=stop_ids,
                    is_deleted=False,
                )
                .exclude(status_evidence_image="")
                .order_by("trip_collection_point_id", "-created_at")
            )
            for event in evidence_events:
                if event.trip_collection_point_id in evidence_by_stop:
                    continue
                url = absolute_image_url(self, event.status_evidence_image)
                if url:
                    evidence_by_stop[event.trip_collection_point_id] = [{
                        "url": url,
                        "trip_collection_point_id": event.trip_collection_point_id,
                        "bin_collection_event_id": event.unique_id,
                        "image_type": "status_evidence",
                    }]
        return [
            {
                "unique_id": related(tcp, "collection_point").unique_id,
                "cp_name": related(tcp, "collection_point").cp_name,
                "sequence": tcp.sequence,
                "is_collected": tcp.is_collected,
                "status": tcp.status,
                "collected_weight_kg": (
                    str(tcp.collected_weight_kg)
                    if tcp.collected_weight_kg is not None
                    else None
                ),
                "waste_type_breakdown": breakdown_by_stop.get(tcp.unique_id, []),
                "capture_images": evidence_by_stop.get(tcp.unique_id, []),
            }
            for tcp in cps
            if tcp.collection_point_id
        ]

    def get_collection_status(self, obj):
        assignment = self._assignment(obj)
        if not assignment:
            return "Not Started"
        bin_stops = self._bin_stops(assignment)
        hh_stops = self._households(assignment)
        total = len(bin_stops) + len(hh_stops)
        if total == 0:
            return "Not Started"
        collected = (
            sum(1 for cp in bin_stops if cp.is_collected)
            + sum(1 for hh in hh_stops if hh.is_collected)
        )
        if collected == 0:
            return "Not Started"
        if collected == total:
            return "Completed"
        return "In Progress"

    def get_household_collections(self, obj):
        assignment = self._assignment(obj)
        if not assignment:
            return []
        result = []
        for hh in self._households(assignment):
            waste = related(hh, "waste_collection")
            customer = related(hh, "customer") or getattr(waste, "customer", None)
            waste_type_breakdown = []
            if waste:
                for column, label in (
                    ("wet_waste", "Wet Waste"),
                    ("dry_waste", "Dry Waste"),
                    ("mixed_waste", "Mixed Waste"),
                    ("sanitary_waste", "Sanitary Waste"),
                ):
                    value = getattr(waste, column, None)
                    if not value:
                        continue
                    waste_type_breakdown.append({
                        "waste_type_name": label,
                        "collected_weight_kg": str(value),
                    })
            result.append({
                "unique_id": hh.unique_id,
                "sequence": hh.sequence,
                "customer_name": getattr(customer, "customer_name", None) if customer else None,
                "customer_unique_id": getattr(customer, "unique_id", None) if customer else None,
                "is_collected": hh.is_collected,
                "collected_weight_kg": (
                    str(hh.collected_weight_kg) if hh.collected_weight_kg is not None else None
                ),
                "wet_waste": str(waste.wet_waste) if waste and waste.wet_waste else None,
                "dry_waste": str(waste.dry_waste) if waste and waste.dry_waste else None,
                "mixed_waste": str(waste.mixed_waste) if waste and waste.mixed_waste else None,
                "sanitary_waste": str(waste.sanitary_waste) if waste and waste.sanitary_waste else None,
                "waste_type_breakdown": waste_type_breakdown,
                "collected_at": hh.collected_at.isoformat() if hh.collected_at else None,
                "status": hh.status,
                "capture_images": self._household_status_evidence(hh),
            })
        return result

    def _household_status_evidence(self, household):
        url = absolute_image_url(self, household.status_evidence_image)
        if not url:
            return []
        return [{
            "url": url,
            "household_collection_id": household.unique_id,
            "trip_household_collection_id": household.unique_id,
            "image_type": "status_evidence",
        }]

    def get_capture_images(self, obj):
        """Capture photos taken during this trip — aggregated by matching every
        household collection's customer + collection date against
        WasteCollectionSub photos (there is no direct FK to the photo)."""
        assignment = self._assignment(obj)
        if not assignment:
            return []
        request = self.context.get("request")
        images = []
        seen = set()
        pairs = [
            (
                getattr(related(hh, "customer"), "unique_id", None),
                getattr(related(hh, "waste_collection"), "collection_date", None),
            )
            for hh in self._households(assignment)
        ]
        for household_images in capture_images_for_customers(pairs, request):
            for img in household_images:
                if img["url"] not in seen:
                    seen.add(img["url"])
                    images.append(img)
        return images

    def get_waste_type_breakdown(self, obj):
        assignment = self._assignment(obj)
        if not assignment:
            return []
        rows = assignment.__dict__.get("_waste_breakdown_cache")
        if rows is None:
            rows = bulk_waste_type_rows_for_trip_assignments([assignment.unique_id], source="all")
        return [
            {
                "waste_type_name": row["waste_type_name"],
                "collected_weight_kg": str(row["weight_kg"]),
            }
            for row in rows
        ]

    def _resolve_panchayat(self, obj):
        assignment = self._assignment(obj)
        trip_plan = self._trip_plan(assignment)
        panchayat_id = (
            obj.panchayat_id
            or getattr(assignment, "panchayat_id", None)
            or getattr(trip_plan, "panchayat_id", None)
        )
        if not panchayat_id:
            return None
        from app.models.masters.panchayat import Panchayat
        return self._lookup(Panchayat, panchayat_id)

    def _resolve_zone(self, obj):
        assignment = self._assignment(obj)
        trip_plan = self._trip_plan(assignment)
        zone_id = obj.zone_id or getattr(trip_plan, "zone_id", None)
        if not zone_id:
            return None
        from app.models.masters.zone import Zone
        return self._lookup(Zone, zone_id)

    def get_panchayat(self, obj):
        p = self._resolve_panchayat(obj)
        return None if not p else {"unique_id": p.unique_id, "panchayat_name": p.panchayat_name}

    def get_zone(self, obj):
        z = self._resolve_zone(obj)
        return None if not z else {"unique_id": z.unique_id, "zone_name": z.zone_name}

    def get_ward(self, obj):
        assignment = self._assignment(obj)
        if not assignment:
            return None
        wards = self._wards(assignment)
        return [{"unique_id": w.unique_id, "ward_name": w.ward_name} for w in wards] or None

    def get_location(self, obj):
        assignment = self._assignment(obj)
        trip_plan = self._trip_plan(assignment)
        district = related(trip_plan, "district") if trip_plan else None
        city = related(trip_plan, "city") if trip_plan else None
        panchayat = self._resolve_panchayat(obj)
        zone = self._resolve_zone(obj)
        return {
            "district": getattr(district, "name", None),
            "city": getattr(city, "name", None),
            "panchayat": getattr(panchayat, "panchayat_name", None),
            "zone": getattr(zone, "zone_name", None),
            "local_body_name": getattr(panchayat, "panchayat_name", None) or getattr(zone, "zone_name", None),
            "local_body_level": "Panchayat" if panchayat else ("Zone" if zone else None),
        }

    def get_collection_point(self, obj):
        cp = related(obj, "collection_point")
        return None if not cp else {"unique_id": cp.unique_id, "cp_name": cp.cp_name}

    def get_waste_type(self, obj):
        wt = related(obj, "waste_type")
        return None if not wt else {"unique_id": wt.unique_id, "waste_type_name": wt.waste_type_name}

    def get_waste_types_detail(self, obj):
        """Every waste type this trip collects.

        Trip creation writes the selected waste types to the assignment's
        `waste_type_ids` JSON list, while other flows fill the `waste_types`
        M2M, so reading either one alone drops types the trip really carries.
        `_assignment_waste_type_ids` is the same union the operator-mobile bin
        scan validates against, which keeps the log consistent with what the
        app accepts.
        """
        from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
        from app.viewsets.operator_mobile.helpers import _assignment_waste_type_ids

        assignment = self._assignment(obj)
        if not assignment:
            return []
        ids = _assignment_waste_type_ids(assignment, trip_plan=self._trip_plan(assignment))
        if not ids:
            return []
        # Preserve the order the trip declared them in, then append any that
        # only the M2M/trip-plan knows about.
        ordered = [str(v) for v in (assignment.waste_type_ids or []) if str(v) in ids]
        ordered += sorted(ids - set(ordered))
        by_id = getattr(self, "_waste_types_by_id", None)
        if by_id is None:
            by_id = {
                wt.unique_id: wt
                for wt in WasteType.objects.filter(unique_id__in=ids, is_deleted=False)
            }
        return [
            {
                "unique_id": waste_type_id,
                "waste_type_name": by_id[waste_type_id].waste_type_name,
            }
            for waste_type_id in ordered
            if waste_type_id in by_id
        ]

    def _staff_dict(self, staff):
        if not staff:
            return None
        return {
            "staff_unique_id": staff.staff_unique_id,
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }

    def get_driver(self, obj):
        return self._staff_dict(related(obj, "driver"))

    def get_operator(self, obj):
        return self._staff_dict(related(obj, "operator"))

    def get_extra_operators(self, obj):
        if not obj.extra_operator_ids:
            return []
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        ids = [o for o in obj.extra_operator_ids.split(",") if o]
        return [self._staff_dict(staff) for staff in StaffcreationOfficeDetails.objects.filter(staff_unique_id__in=ids)]

    def get_vehicle(self, obj):
        vehicle = related(obj, "vehicle")
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": str(vehicle.capacity) if vehicle.capacity is not None else None,
        }

    def get_bins(self, obj):
        if not obj.bin_ids:
            return []
        from app.models.masters.waste_masters.bins import Bins
        ids = [b for b in obj.bin_ids.split(",") if b]
        return [
            {
                "unique_id": bin_obj.unique_id,
                "bin_name": bin_obj.bin_name,
                "bin_status": getattr(bin_obj, "bin_status", None),
            }
            for bin_obj in Bins.objects.filter(unique_id__in=ids)
        ]

    def get_verified_by_name(self, obj):
        account = obj.verified_by_user
        staff = getattr(account, "staff", None)
        user = getattr(account, "user", None)
        return getattr(staff, "employee_name", None) or getattr(user, "username", None)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance and instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            raise serializers.ValidationError("Verified trip logs are read-only.")

        # trip_assignment_id here is the plain unique_id string
        # (UniqueIdOrPkField.to_internal_value already normalises it) —
        # resolve the actual row before touching anything but the id.
        assignment = attrs.get(
            "trip_assignment_id",
            getattr(instance, "trip_assignment_id", None),
        )
        assignment_obj = (
            DailyTripAssignment.objects.filter(unique_id=assignment).first()
            if assignment else None
        )
        if assignment_obj and assignment_obj.status == DailyTripAssignment.STATUS_CANCELLED:
            raise serializers.ValidationError("Cannot create a log for a cancelled trip.")

        if assignment and not instance:
            if DailyTripLog.objects.filter(trip_assignment_id=assignment, is_deleted=False).exists():
                raise serializers.ValidationError("A log already exists for this trip assignment.")

        start_time = attrs.get("actual_start_time", getattr(instance, "actual_start_time", None))
        end_time = attrs.get("actual_end_time", getattr(instance, "actual_end_time", None))
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError("actual_end_time must be after actual_start_time.")

        return attrs


class DailyTripLogVerifySerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        instance = self.context.get("instance")
        if instance and instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            raise serializers.ValidationError("Trip log is already verified.")
        if instance and not instance.actual_end_time:
            raise serializers.ValidationError(
                "This trip hasn't ended yet — actual end time is required before it can be verified."
            )
        return attrs

    def save(self, **kwargs):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks")
        now = timezone.now()

        update_fields = {
            "log_status": DailyTripLog.LOG_STATUS_VERIFIED,
            "verified_by": account.account_id if account else None,
            "verified_at": now,
            "updated_at": now,
        }
        if remarks:
            update_fields["remarks"] = remarks

        DailyTripLog.objects.filter(pk=instance.pk).update(**update_fields)
        instance.refresh_from_db()
        return instance
