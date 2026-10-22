import json
from dataclasses import dataclass
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.staff_management.staffcreation import Staffcreation


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


def _template_ids_for_staff(staff: Staffcreation):
    return set(
        StaffTemplate.objects.filter(
            Q(operator_id=staff.staff_unique_id) | Q(driver_id=staff.staff_unique_id)
        ).values_list("unique_id", flat=True)
    )


def _alternative_template_ids_for_staff(staff: Staffcreation):
    return set(
        AlternativeStaffTemplate.objects.filter(
            Q(operator_id=staff.staff_unique_id) | Q(driver_id=staff.staff_unique_id)
        ).values_list("unique_id", flat=True)
    )


def _effective_staff_q(staff: Staffcreation) -> Q:
    """Match this staff against whichever template is currently in force.

    A vehicle breakdown can substitute the crew via `alt_staff_template_id`;
    when that's set, ONLY the alt crew is "effective" for the trip — the
    original crew's own login should no longer resolve it as theirs.

    Both assignment template fields are plain unique-id strings, not FKs, so
    resolve the matching template ids first and filter those id columns
    directly. Do not use `staff_template_id__driver_id` style traversal here.
    """
    template_ids = _template_ids_for_staff(staff)
    alt_template_ids = _alternative_template_ids_for_staff(staff)
    query = Q(pk__in=[])
    if alt_template_ids:
        query |= Q(alt_staff_template_id__in=alt_template_ids)
    if template_ids:
        query |= (
            Q(alt_staff_template_id__isnull=True)
            & Q(staff_template_id__in=template_ids)
        )
    return query


def _effective_extra_operator_ids(assignment: DailyTripAssignment):
    source = assignment.alt_staff_template or assignment.staff_template
    return getattr(source, "extra_operator_id", None) or []


def find_assignments_for_operator_today(staff: Staffcreation):
    today = timezone.localdate()
    base = (
        DailyTripAssignment.objects
        .filter(trip_date=today, is_deleted=False)
        .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
        .order_by("scheduled_time", "unique_id")
    )

    candidates = list(base.filter(_effective_staff_q(staff)))
    extra_operator_matches = [
        candidate for candidate in base
        if staff.staff_unique_id in (_effective_extra_operator_ids(candidate) or [])
    ]
    seen = {candidate.unique_id for candidate in candidates}
    candidates.extend(
        candidate
        for candidate in extra_operator_matches
        if candidate.unique_id not in seen
    )
    return candidates


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
    # The driver ("captain") and operator apps were merged — one phone per
    # vehicle — so a trip belongs to this staff member whether they are the
    # template's driver OR its operator. Mirrors IsOperatorRole, which accepts
    # both roles.
    candidates = find_assignments_for_operator_today(staff)

    if not candidates:
        raise OperatorFlowError(
            "NO_ACTIVE_TRIP",
            "No trip is assigned to you for today.",
        )

    if collection_type:
        of_type = [
            candidate for candidate in candidates
            if getattr(candidate.trip_plan, "collection_type", None)
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
    ids = set(str(v) for v in (assignment.waste_type_ids or []) if v)
    if assignment.trip_plan_id:
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        plan = TripPlan.objects.filter(unique_id=assignment.trip_plan_id).first()
        if plan and plan.waste_type_id:
            ids.add(str(plan.waste_type_id))
    return {str(i) for i in ids if i}


def _assignment_waste_type_names(assignment: DailyTripAssignment) -> str:
    """Human-readable list of the trip's waste types, for error messages."""
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType

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
    if trip_waste_type_ids and str(bin_obj.wastetype_id) not in trip_waste_type_ids:
        bin_waste = getattr(bin_obj.wastetype_id, "waste_type_name", "unknown")
        trip_waste_names = _assignment_waste_type_names(assignment) or "unknown"
        raise OperatorFlowError(
            "WRONG_WASTE_TYPE",
            f"This bin is {bin_waste}; your trip collects {trip_waste_names}.",
        )

    cp = bin_obj.collection_point
    cp_id = getattr(cp, "unique_id", None) or bin_obj.collection_point_id

    # Geo guard: only enforced when BOTH the trip and the collection point
    # are panchayat-scoped. Unlike government (where every trip is panchayat
    # based), this project also runs zone/ward-scoped trips whose assignment
    # carries no panchayat at all — comparing None against the CP's panchayat
    # rejected every legitimate scan on those trips. The authoritative
    # "is this bin on my trip" check is the DailyTripCollectionPoint lookup
    # below, which is exact; this is only a friendlier early error.
    #
    # It must ALSO stand down when this exact CP is genuinely one of the
    # assignment's stops, even if its panchayat differs from
    # `assignment.panchayat_id` — a single-panchayat bin round is the norm,
    # but it is not guaranteed: BluePlanetSeeder's demo bin trip deliberately
    # visits CPs across three different panchayats (GNO PLB 1/2/3) under one
    # assignment that only records the first as `panchayat_id`. Without this
    # exists() check every scan on CP 2 or 3 of that trip was rejected as
    # "outside your assigned panchayat" despite being squarely on the trip —
    # the exact case the CP_NOT_IN_TRIP lookup below would have accepted.
    cp_panchayat_id = getattr(cp, "panchayat_id", None)
    if (
        assignment.panchayat_id
        and cp_panchayat_id
        and str(cp_panchayat_id) != str(assignment.panchayat_id)
        and not DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment.unique_id,
            collection_point_id=cp_id,
            is_deleted=False,
        ).exists()
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
            trip_assignment_id=assignment.unique_id,
            collection_point_id=cp_id,
            bin_id=bin_obj.unique_id,
            is_deleted=False,
        )
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
    raise_if_stop_unwritable(assignment, trip_cp)

    return trip_cp


def raise_if_stop_unwritable(assignment, stop):
    """Refuse a driver write on a closed trip, or on a stop a Re-Trip /
    breakdown moved to a continuation.

    An app that has not refreshed since the approval still shows the source
    trip; without this, a collect there would land on the source row while
    the continuation's copy stays Pending, and the stop gets visited twice.
    """
    if assignment.status in (
        DailyTripAssignment.STATUS_COMPLETED,
        DailyTripAssignment.STATUS_CANCELLED,
    ):
        raise OperatorFlowError(
            "TRIP_CLOSED",
            "This trip has ended. Refresh your trip list.",
            http_status=409,
        )
    if stop.carried_to_assignment:
        raise OperatorFlowError(
            "STOP_CARRIED_OVER",
            f"This stop moved to your next trip ({stop.carried_to_assignment}). "
            "Refresh your trip list.",
            http_status=409,
        )


def lock_stop_for_write(assignment, stop):
    """Re-read the trip and the stop under row locks and re-check them.

    Call inside the write's transaction. Trip first, then stop — the order
    Re-Trip approval uses — so a scan racing an approval waits for it and
    then sees the stop as carried over instead of collecting it on the
    source too. Returns the locked stop.
    """
    locked_assignment = DailyTripAssignment.objects.select_for_update().get(
        pk=assignment.pk
    )
    locked_stop = type(stop).objects.select_for_update().get(pk=stop.pk)
    if locked_stop.is_collected:
        raise OperatorFlowError(
            "ALREADY_COLLECTED",
            "This stop has already been marked collected.",
            http_status=409,
        )
    raise_if_stop_unwritable(locked_assignment, locked_stop)
    return locked_stop


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
    from app.models.core_modules.schedule_setup.trip_plan import TripPlan

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
    # trip_assignment_id is a plain CharField (DailyTripAssignment.unique_id)
    # now, not a real FK, so it can't be traversed with `__` lookups or
    # select_related. Filter by today's assignments explicitly, then resolve
    # the winning row's assignment through the model's resolver property.
    today_assignment_ids = set(
        DailyTripAssignment.objects.filter(
            trip_date=timezone.localdate(),
            is_deleted=False,
        ).values_list("unique_id", flat=True)
    )
    active_assignment_id = getattr(active_assignment, "unique_id", active_assignment)
    other = (
        DailyTripCollectionPoint.objects
        .filter(
            bin_id=bin_obj.unique_id,
            is_deleted=False,
            trip_assignment_id__in=today_assignment_ids,
        )
        .exclude(trip_assignment_id=active_assignment_id)
        .first()
    )
    if not other:
        return
    other_assignment = other.trip_assignment
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
    # Template ids are plain CharFields now — resolve the actual template row
    # through the model's resolver property instead.
    template = assignment.alt_staff_template or assignment.staff_template
    if template is None:
        return False
    if staff.staff_unique_id in (
        getattr(template, "driver_id", None),
        getattr(template, "operator_id", None),
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
    waste_type = bin_obj.wastetype
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
            "unique_id": bin_obj.wastetype_id,
            "name": getattr(waste_type, "waste_type_name", None),
        },
    }


def serialize_cp_brief(cp) -> dict:
    if isinstance(cp, str):
        from app.models.core_modules.schedule_setup.collection_point import Collection_point
        cp = Collection_point.objects.filter(unique_id=cp).first()
    if cp is None:
        return None
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
    panchayat = assignment.panchayat
    ward = assignment.wards.first()
    waste_type = assignment.primary_waste_type
    vehicle = assignment.vehicle
    waste_type_obj = None
    if waste_type:
        from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
        waste_type_obj = WasteType.objects.filter(unique_id=waste_type).first()
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
                "unique_id": waste_type_obj.unique_id,
                "name": waste_type_obj.waste_type_name,
            }
            if waste_type_obj
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
    template = assignment.staff_template
    driver_id = getattr(template, "driver_id", None)
    if not driver_id:
        return None
    return Staffcreation.objects.filter(staff_unique_id=driver_id).first()


def resolve_customer_from_id(customer_id: str):
    """The CustomerCreation behind whatever id form the app sends.

    The app sends either the customer's `unique_id` (scanned QR / trip
    payload) or the legacy `customer_id` column, so match on both — the same
    pair every other household endpoint in this project matches on.
    """
    from app.models.masters.customer_masters.customercreation import CustomerCreation

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
    from app.models.core_modules.daily_operations.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )

    customer_company_id = getattr(customer, "company_id_id", None)
    customer_project_id = getattr(customer, "project_id_id", None)
    if (
        customer_project_id
        and assignment.project_id
        and str(customer_project_id) != str(assignment.project_id)
    ):
        raise OperatorFlowError(
            "WRONG_PROJECT",
            "This customer belongs to a different project.",
            http_status=403,
        )
    if (
        customer_company_id
        and assignment.company_id
        and str(customer_company_id) != str(assignment.company_id)
    ):
        raise OperatorFlowError(
            "WRONG_COMPANY",
            "This customer belongs to a different company.",
            http_status=403,
        )

    stop = (
        DailyTripHouseholdCollection.objects
        .filter(
            trip_assignment_id=assignment.unique_id,
            customer_id=customer.unique_id,
            is_deleted=False,
        )
        .first()
    )
    if stop is None:
        _raise_if_customer_belongs_to_locked_trip(customer, assignment)
        raise OperatorFlowError(
            "CUSTOMER_NOT_IN_TRIP",
            "This household is not on your current trip.",
        )
    # An already-collected stop keeps the callers' own "already collected"
    # answer; only a write that would actually change the stop is refused.
    if not stop.is_collected:
        raise_if_stop_unwritable(assignment, stop)
    return stop


def _raise_if_customer_belongs_to_locked_trip(customer, active_assignment):
    """Mirror of `_raise_if_bin_belongs_to_locked_trip` for households: if the
    customer is a stop on another of today's trips, say so rather than
    claiming they are not on any trip at all."""
    from app.models.core_modules.daily_operations.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )
    from app.models.core_modules.daily_operations.daily_trip_assignment import (
        DailyTripAssignment,
    )

    today_assignment_ids = DailyTripAssignment.objects.filter(
        trip_date=timezone.localdate(),
        is_deleted=False,
    ).values_list("unique_id", flat=True)

    other = (
        DailyTripHouseholdCollection.objects
        .filter(
            customer_id=customer.unique_id,
            is_deleted=False,
            trip_assignment_id__in=today_assignment_ids,
        )
        .exclude(trip_assignment_id=active_assignment.unique_id)
        .first()
    )
    if not other:
        return
    other_assignment = DailyTripAssignment.objects.filter(
        unique_id=other.trip_assignment_id,
        is_deleted=False,
    ).first()
    scheduled = getattr(other_assignment, "scheduled_time", None)
    raise OperatorFlowError(
        "TRIP_LOCKED",
        (
            "This household belongs to your "
            f"{scheduled.strftime('%H:%M') if scheduled else 'other'}"
            " trip. Finish the current trip before starting that one."
        ),
        http_status=409,
    )
