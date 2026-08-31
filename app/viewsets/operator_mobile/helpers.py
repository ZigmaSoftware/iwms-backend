import json
from dataclasses import dataclass
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from app.models.assets.bins import Bins
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.user_creations.staffcreation import Staffcreation


class OperatorFlowError(Exception):
    """Raised when an operator scan/validate fails business rules."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


@dataclass
class ScanContext:
    bin: Bins
    assignment: DailyTripAssignment
    trip_cp: DailyTripCollectionPoint


def resolve_operator_staff(user) -> Staffcreation:
    if not isinstance(user, Staffcreation):
        raise OperatorFlowError(
            "NOT_AN_OPERATOR_ACCOUNT",
            "Authenticated account is not a staff record.",
            http_status=403,
        )
    return user


def _effective_staff_q(staff: Staffcreation) -> Q:
    """Match this staff against whichever template is currently in force.

    A vehicle breakdown can substitute the crew via `alt_staff_template_id`;
    when that's set, ONLY the alt crew is "effective" for the trip — the
    original crew's own login should no longer resolve it as theirs.
    """
    return (
        Q(alt_staff_template_id__isnull=False, alt_staff_template_id__operator_id=staff)
        | Q(alt_staff_template_id__isnull=False, alt_staff_template_id__driver_id=staff)
        | Q(alt_staff_template_id__isnull=True, staff_template_id__operator_id=staff)
        | Q(alt_staff_template_id__isnull=True, staff_template_id__driver_id=staff)
    )


def _effective_extra_operator_ids(assignment: DailyTripAssignment):
    alt = assignment.alt_staff_template_id
    source = alt if alt is not None else assignment.staff_template_id
    return getattr(source, "extra_operator_id", None) or []


def assignment_is_finished(assignment: DailyTripAssignment) -> bool:
    """True when the trip has no work left: it is Completed, or every one of
    its stops (bin + household) is resolved."""
    if assignment.status == DailyTripAssignment.STATUS_COMPLETED:
        return True

    bin_stops = list(assignment.trip_collection_points.filter(is_deleted=False))
    household_stops = list(
        assignment.trip_household_collections.filter(is_deleted=False)
    )
    stops = bin_stops + household_stops
    if not stops:
        return False
    return all(
        stop.is_collected or stop.status != DailyTripCollectionPoint.STATUS_PENDING
        for stop in stops
    )


def find_active_assignment_for_operator(
    staff: Staffcreation,
    collection_type: str | None = None,
) -> DailyTripAssignment:
    """The trip this staff is currently working.

    `collection_type` narrows the search to one kind of trip (bin / household /
    bulk). Sequencing is per TYPE: a crew's bin trips run one after another, but
    an open household trip must not become the answer for a bin scan. When no
    trip of that type exists the filter is ignored, so assignments without a
    trip plan still resolve.
    """
    today = timezone.localdate()

    base = (
        DailyTripAssignment.objects
        .filter(trip_date=today, is_deleted=False)
        .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
        .select_related(
            "panchayat_id",
            "vehicle_id",
            "trip_plan_id",
            "alt_staff_template_id",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__driver_id__staffusertype_id",
            "staff_template_id__driver_id__personal_details",
            "staff_template_id__operator_id",
            "staff_template_id__operator_id__staffusertype_id",
            "staff_template_id__operator_id__personal_details",
        )
        .prefetch_related("waste_types", "wards")
        .order_by("scheduled_time", "unique_id")
    )

    # The driver ("captain") and operator apps were merged — one phone per
    # vehicle — so a trip belongs to this staff member whether they are the
    # template's driver OR its operator. Mirrors IsOperatorRole, which accepts
    # both roles.
    candidates = list(
        base.filter(
            Q(staff_template_id__operator_id=staff)
            | Q(staff_template_id__driver_id=staff)
        )
    )
    if not candidates:
        # Extra-operator fallback: walk staff_templates and check JSON membership in Python
        # (avoids SQLite-incompatible JSON __contains lookups).
        candidates = [
            candidate for candidate in base
            if staff.staff_unique_id
            in (getattr(candidate.staff_template_id, "extra_operator_id", None) or [])
        ]

    if not candidates:
        raise OperatorFlowError(
            "NO_ACTIVE_TRIP",
            "No trip is assigned to you for today.",
        )

    if collection_type:
        of_type = [
            candidate for candidate in candidates
            if getattr(candidate.trip_plan_id, "collection_type", None)
            == collection_type
        ]
        if of_type:
            candidates = of_type

    # The crew runs their trips in order, so "the active trip" is normally the
    # earliest one with work left. When the driver has already pressed Start on
    # one of today's trips, however, that trip is the one in progress and all
    # scans must be validated against it — not merely the earliest unfinished
    # one. Without this, a crew holding a Wet (07:00) and a Dry (09:00) bin trip
    # that presses Start on the Dry trip would still have every scan rejected:
    # the loop would keep pointing at the (unfinished) Wet trip, so a Dry bin
    # would fail the waste-type check as "wrong trip."
    started = [
        c for c in candidates
        if c.status == DailyTripAssignment.STATUS_IN_PROGRESS
    ]
    if started:
        return min(started, key=lambda c: (c.scheduled_time, c.unique_id))

    # No trip started yet → the earliest one with work left is the answer.
    for candidate in candidates:
        if not assignment_is_finished(candidate):
            return candidate
    return candidates[0]


def _extract_bin_identifier(raw: str) -> str:
    """The printed bin QR encodes JSON like {"id": "BIN-..."} (see
    app/utils/bin_qr.py). Card taps in the app instead send the stored bin_qr
    image path. Pull the bin unique_id out of whatever form we receive."""
    raw = (raw or "").strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            return str(data.get("id") or data.get("unique_id") or "").strip()
        except (ValueError, TypeError):
            return raw
    if "/media/bin_qr/" in raw:
        filename = raw.rsplit("/", 1)[-1]
        return filename.rsplit(".", 1)[0]
    if raw.startswith("bin_qr/"):
        filename = raw.rsplit("/", 1)[-1]
        return filename.rsplit(".", 1)[0]
    return raw


def resolve_bin_from_qr(bin_qr: str) -> Bins:
    identifier = _extract_bin_identifier(bin_qr)
    bin_obj = (
        Bins.objects
        .filter(is_deleted=False)
        # Match the decoded unique_id (camera scan / raw id) OR the stored
        # bin_qr image path (app card-tap sends the path from my-trip-today).
        .filter(Q(unique_id=identifier) | Q(bin_qr=bin_qr))
        .select_related("collection_point_id", "collection_point_id__panchayat_id", "wastetype_id")
        .first()
    )
    if not bin_obj:
        raise OperatorFlowError(
            "BIN_NOT_FOUND",
            f"No bin found for QR '{bin_qr}'.",
            http_status=404,
        )
    return bin_obj


def _assignment_waste_type_ids(assignment: DailyTripAssignment) -> set:
    """Every waste-type id this trip collects, from all three storage spots.

    Returns an empty set when the trip declares none anywhere, which callers
    treat as "unrestricted" rather than "collects nothing" — a trip with no
    declared waste type should not reject every bin.
    """
    ids = set(assignment.waste_types.values_list("unique_id", flat=True))
    ids.update(str(v) for v in (assignment.waste_type_ids or []) if v)
    plan_waste_type_id = getattr(assignment.trip_plan_id, "waste_type_id_id", None)
    if plan_waste_type_id:
        ids.add(str(plan_waste_type_id))
    return {str(i) for i in ids if i}


def _assignment_waste_type_names(assignment: DailyTripAssignment) -> str:
    """Human-readable list of the trip's waste types, for error messages."""
    from app.models.user_creations.waste_collection_bluetooth import WasteType

    ids = _assignment_waste_type_ids(assignment)
    if not ids:
        return ""
    names = WasteType.objects.filter(unique_id__in=ids).values_list(
        "waste_type_name", flat=True
    )
    return ", ".join(sorted(n for n in names if n))


def validate_bin_against_assignment(
    bin_obj: Bins, assignment: DailyTripAssignment
) -> DailyTripCollectionPoint:
    # A trip can carry multiple waste types, and this project stores them in
    # more than one place: the `waste_types` M2M, the `waste_type_ids` JSON
    # list, and (single) `TripPlan.waste_type_id`. Different seeders/flows
    # populate different ones, so read all of them — keying off the M2M alone
    # rejected every scan on trips where only the JSON list was filled.
    trip_waste_type_ids = _assignment_waste_type_ids(assignment)
    if trip_waste_type_ids and str(bin_obj.wastetype_id_id) not in trip_waste_type_ids:
        bin_waste = getattr(bin_obj.wastetype_id, "waste_type_name", "unknown")
        trip_waste_names = _assignment_waste_type_names(assignment) or "unknown"
        raise OperatorFlowError(
            "WRONG_WASTE_TYPE",
            f"This bin is {bin_waste}; your trip collects {trip_waste_names}.",
        )

    cp = bin_obj.collection_point_id

    # Geo guard: only enforced when BOTH the trip and the collection point
    # are panchayat-scoped. Unlike government (where every trip is panchayat
    # based), this project also runs zone/ward-scoped trips whose assignment
    # carries no panchayat at all — comparing None against the CP's panchayat
    # rejected every legitimate scan on those trips. The authoritative
    # "is this bin on my trip" check is the DailyTripCollectionPoint lookup
    # below, which is exact; this is only a friendlier early error.
    cp_panchayat_id = getattr(cp, "panchayat_id_id", None)
    if (
        assignment.panchayat_id_id
        and cp_panchayat_id
        and str(cp_panchayat_id) != str(assignment.panchayat_id_id)
    ):
        raise OperatorFlowError(
            "WRONG_PANCHAYAT",
            "This bin is outside your assigned panchayat.",
        )

    # Match on the bin too: a collection point can hold several bins (one per
    # waste type), and without this the wrong row is returned/marked.
    trip_cp = (
        DailyTripCollectionPoint.objects
        .filter(
            trip_assignment_id=assignment,
            collection_point_id=cp,
            bin_id=bin_obj,
            is_deleted=False,
        )
        .select_related("collection_point_id", "bin_id")
        .first()
    )
    if not trip_cp:
        raise OperatorFlowError(
            "CP_NOT_IN_TRIP",
            "This bin is not part of your assigned collection points.",
        )

    if trip_cp.is_collected:
        raise OperatorFlowError(
            "ALREADY_COLLECTED",
            "This collection point has already been marked collected.",
            http_status=409,
        )

    return trip_cp


def require_trip_started(assignment: DailyTripAssignment) -> None:
    """Gate every collection write (bin scan, skip/not-available) on the
    driver having explicitly pressed Start.

    Without this, a scan could silently start the trip as a side effect,
    making "Start Trip" purely cosmetic. Raises `OperatorFlowError`
    (`TRIP_NOT_STARTED`, 409) when the assignment has no `actual_start_at`
    yet. A Completed/Cancelled trip is not this guard's concern — callers
    already reject those earlier with their own specific codes.
    """
    if not assignment.actual_start_at:
        raise OperatorFlowError(
            "TRIP_NOT_STARTED",
            "Start the trip before collecting. Press \"Start Trip\" first.",
            http_status=409,
        )


def build_scan_context(bin_qr: str, operator: Staffcreation) -> ScanContext:
    from app.models.schedule_masters.trip_plan import TripPlan

    # A bin scan belongs to a BIN trip: with a household trip open at the same
    # time, an untyped lookup would hand the scan to the household trip and the
    # bin would always fail its waste-type / stop-membership check.
    assignment = find_active_assignment_for_operator(
        operator, collection_type=TripPlan.COLLECTION_TYPE_BIN
    )
    bin_obj = resolve_bin_from_qr(bin_qr)
    try:
        trip_cp = validate_bin_against_assignment(bin_obj, assignment)
    except OperatorFlowError as exc:
        if exc.code == "CP_NOT_IN_TRIP":
            # The bin may belong to a LATER trip of the same crew (e.g. the
            # 15:00 bin run while the 07:00 one is still open). "Not part of
            # your collection points" reads like a mis-scan; say what is
            # actually blocking it.
            _raise_if_bin_belongs_to_locked_trip(bin_obj, operator, assignment)
        raise
    return ScanContext(bin=bin_obj, assignment=assignment, trip_cp=trip_cp)


def _raise_if_bin_belongs_to_locked_trip(bin_obj, operator, active_assignment):
    """If this bin is a stop on another of today's trips for the same crew,
    explain that the earlier trip must be finished first."""
    other = (
        DailyTripCollectionPoint.objects
        .filter(
            bin_id=bin_obj,
            is_deleted=False,
            trip_assignment_id__trip_date=timezone.localdate(),
            trip_assignment_id__is_deleted=False,
        )
        .exclude(trip_assignment_id=active_assignment)
        .select_related("trip_assignment_id")
        .first()
    )
    if not other:
        return
    other_assignment = other.trip_assignment_id
    if not _staff_owns_assignment(other_assignment, operator):
        return
    raise OperatorFlowError(
        "TRIP_LOCKED",
        (
            "This bin belongs to your "
            f"{other_assignment.scheduled_time.strftime('%H:%M') if other_assignment.scheduled_time else 'later'}"
            " trip. Finish the current trip before starting that one."
        ),
        http_status=409,
    )


def _staff_owns_assignment(assignment: DailyTripAssignment, staff: Staffcreation) -> bool:
    template = assignment.staff_template_id
    if template is None:
        return False
    if staff.staff_unique_id in (
        getattr(template, "driver_id_id", None),
        getattr(template, "operator_id_id", None),
    ):
        return True
    return staff.staff_unique_id in (
        getattr(template, "extra_operator_id", None) or []
    )


def progress_payload(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(1 for c in children if c.is_collected)
    return {
        "collected": collected,
        "total": total,
        "completed": total > 0 and collected == total,
    }


def _bin_qr_image_url(bin_obj: Bins, request=None):
    qr = getattr(bin_obj, "bin_qr", None)
    try:
        url = qr.url if qr else None
    except (ValueError, AttributeError):
        url = None
    if not url:
        return None
    return request.build_absolute_uri(url) if request is not None else url


def serialize_bin_brief(bin_obj: Bins, request=None) -> dict:
    return {
        "unique_id": bin_obj.unique_id,
        "bin_name": bin_obj.bin_name,
        # The app sends this value back to validate/scan. Keep it as the stable
        # bin identifier; the PNG URL is exposed separately for display.
        # (Returning the raw ImageField here made DRF try to JSON-encode the
        # PNG bytes and 500 with a UnicodeDecodeError.)
        "bin_qr": bin_obj.unique_id,
        "bin_qr_image_url": _bin_qr_image_url(bin_obj, request=request),
        "bin_capacity": bin_obj.bin_capacity,
        "waste_type": {
            "unique_id": bin_obj.wastetype_id_id,
            "name": getattr(bin_obj.wastetype_id, "waste_type_name", None),
        },
    }


def serialize_cp_brief(cp) -> dict:
    return {
        "unique_id": cp.unique_id,
        "name": cp.cp_name,
        "latitude": str(cp.latitude) if cp.latitude is not None else None,
        "longitude": str(cp.longitude) if cp.longitude is not None else None,
    }


def serialize_trip_cp_brief(trip_cp: DailyTripCollectionPoint) -> dict:
    return {
        "unique_id": trip_cp.unique_id,
        "sequence": trip_cp.sequence,
        "is_collected": trip_cp.is_collected,
        "status": trip_cp.status,
        "collected_at": trip_cp.collected_at.isoformat() if trip_cp.collected_at else None,
        "collected_weight_kg": (
            str(trip_cp.collected_weight_kg)
            if trip_cp.collected_weight_kg is not None
            else None
        ),
    }


def serialize_assignment_brief(assignment: DailyTripAssignment) -> dict:
    panchayat = assignment.panchayat_id
    ward = assignment.wards.first()
    waste_type = assignment.primary_waste_type
    vehicle = assignment.vehicle_id
    return {
        "unique_id": assignment.unique_id,
        "status": assignment.status,
        "trip_date": assignment.trip_date.isoformat(),
        # Nullable: this project also runs zone/ward-scoped trips, which carry
        # no panchayat at all.
        "panchayat": (
            {
                "unique_id": panchayat.unique_id,
                "name": panchayat.panchayat_name,
            }
            if panchayat
            else None
        ),
        "ward": (
            {
                "unique_id": ward.unique_id,
                "name": ward.ward_name,
            }
            if ward
            else None
        ),
        "waste_type": (
            {
                "unique_id": waste_type.unique_id,
                "name": waste_type.waste_type_name,
            }
            if waste_type
            else None
        ),
        "vehicle": (
            {
                "unique_id": vehicle.unique_id,
                "vehicle_no": vehicle.vehicle_no,
                "capacity": str(vehicle.capacity),
            }
            if vehicle
            else None
        ),
    }


def maybe_resolve_driver(assignment: DailyTripAssignment) -> Optional[Staffcreation]:
    template = assignment.staff_template_id
    return getattr(template, "driver_id", None)


def resolve_customer_from_id(customer_id: str):
    """The CustomerCreation behind whatever id form the app sends.

    The app sends either the customer's `unique_id` (scanned QR / trip
    payload) or the legacy `customer_id` column, so match on both — the same
    pair every other household endpoint in this project matches on.
    """
    from app.models.customers.customercreation import CustomerCreation

    identifier = (customer_id or "").strip()
    if not identifier:
        raise OperatorFlowError("CUSTOMER_ID_REQUIRED", "customer_id is required.")

    customer = (
        CustomerCreation.objects
        .filter(
            Q(unique_id=identifier) | Q(customer_id=identifier),
            is_deleted=False,
        )
        .first()
    )
    if customer is None:
        raise OperatorFlowError(
            "CUSTOMER_NOT_FOUND",
            f"No customer found for '{identifier}'.",
            http_status=404,
        )
    return customer


def validate_customer_against_assignment(customer, assignment):
    """The household counterpart to `validate_bin_against_assignment`.

    Returns the `DailyTripHouseholdCollection` stop this customer occupies on
    `assignment`, or raises. Two separate rules, in the order a driver hits
    them:

    1. PROJECT scope — the customer must belong to the same company/project
       as the trip. A customer from another project is never collectable,
       whatever trip is open.
    2. TRIP membership — the customer must already be a stop on this
       assignment. Previously the household endpoints attached any scanned
       customer to the live trip on the fly, which is exactly how a household
       that was never planned for this trip got collected without complaint.

    A customer legitimately on a LATER trip of the same crew gets the
    friendlier `TRIP_LOCKED` message instead, so "finish your current trip"
    never reads as "this QR is invalid".
    """
    from app.models.schedule_masters.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )

    customer_company_id = getattr(customer, "company_id_id", None)
    customer_project_id = getattr(customer, "project_id_id", None)
    if (
        customer_project_id
        and assignment.project_id_id
        and str(customer_project_id) != str(assignment.project_id_id)
    ):
        raise OperatorFlowError(
            "WRONG_PROJECT",
            "This customer belongs to a different project.",
            http_status=403,
        )
    if (
        customer_company_id
        and assignment.company_id_id
        and str(customer_company_id) != str(assignment.company_id_id)
    ):
        raise OperatorFlowError(
            "WRONG_COMPANY",
            "This customer belongs to a different company.",
            http_status=403,
        )

    stop = (
        DailyTripHouseholdCollection.objects
        .filter(
            trip_assignment_id=assignment,
            customer_id=customer,
            is_deleted=False,
        )
        .select_related("customer_id")
        .first()
    )
    if stop is None:
        _raise_if_customer_belongs_to_locked_trip(customer, assignment)
        raise OperatorFlowError(
            "CUSTOMER_NOT_IN_TRIP",
            "This household is not on your current trip.",
        )
    return stop


def _raise_if_customer_belongs_to_locked_trip(customer, active_assignment):
    """Mirror of `_raise_if_bin_belongs_to_locked_trip` for households: if the
    customer is a stop on another of today's trips, say so rather than
    claiming they are not on any trip at all."""
    from app.models.schedule_masters.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )

    other = (
        DailyTripHouseholdCollection.objects
        .filter(
            customer_id=customer,
            is_deleted=False,
            trip_assignment_id__trip_date=timezone.localdate(),
            trip_assignment_id__is_deleted=False,
        )
        .exclude(trip_assignment_id=active_assignment)
        .select_related("trip_assignment_id")
        .first()
    )
    if not other:
        return
    other_assignment = other.trip_assignment_id
    scheduled = other_assignment.scheduled_time
    raise OperatorFlowError(
        "TRIP_LOCKED",
        (
            "This household belongs to your "
            f"{scheduled.strftime('%H:%M') if scheduled else 'other'}"
            " trip. Finish the current trip before starting that one."
        ),
        http_status=409,
    )
