"""Helpers used by every operator-mobile viewset.

The backend team replaced the textual `bin_qr` column with an `ImageField`
holding the printed QR PNG; the QR payload encodes `{"id": "<bin.unique_id>"}`.
So bin lookup is now keyed off the bin's `unique_id`, not the file path. We
also support panchayat XOR ward trips and the new `BinCollectionEvent` shape
(no operator_id / driver_id / scanned_qr / event_at — uses created_at and
driver_latitude / driver_longitude).
"""

import json
from dataclasses import dataclass

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


# ---------------------------------------------------------------------------
# Auth resolution
# ---------------------------------------------------------------------------

def resolve_operator_staff(user) -> Staffcreation:
    if not isinstance(user, Staffcreation):
        raise OperatorFlowError(
            "NOT_AN_OPERATOR_ACCOUNT",
            "Authenticated account is not a staff record.",
            http_status=403,
        )
    return user


def _today_assignment_base():
    today = timezone.localdate()
    return (
        DailyTripAssignment.objects
        .filter(trip_date=today, is_deleted=False)
        .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
        .select_related(
            "panchayat_id",
            "ward_id",
            "waste_type_id",
            "vehicle_id",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__operator_id",
            "alt_staff_template_id",
            "alt_staff_template_id__driver_id",
            "alt_staff_template_id__operator_id",
        )
        # Deterministic ordering is what keeps the operator and the driver on
        # the SAME trip when a template has more than one assignment today.
        # Both resolvers query this identical base, so a stable order means
        # `.first()` returns the same row for both roles. Earliest scheduled
        # trip first; unique_id breaks ties so the choice never flip-flops.
        .order_by("scheduled_time", "unique_id")
    )


def find_active_assignment_for_operator(staff: Staffcreation) -> DailyTripAssignment:
    base = _today_assignment_base()

    # Primary: operator listed on the active staff template
    assignment = base.filter(staff_template_id__operator_id=staff).first()

    # Alternative staff template (substitution active today)
    if assignment is None:
        assignment = base.filter(alt_staff_template_id__operator_id=staff).first()

    # Extra-operator fallback — JSON list checked in Python so this works on
    # both MySQL (prod) and SQLite (tests).
    if assignment is None:
        for candidate in base:
            extras = (
                getattr(candidate.staff_template_id, "extra_operator_id", None) or []
            )
            if staff.staff_unique_id in extras:
                assignment = candidate
                break

    if not assignment:
        raise OperatorFlowError(
            "NO_ACTIVE_TRIP",
            "No trip is assigned to you for today.",
        )
    return assignment


def find_active_assignment_for_driver(staff: Staffcreation) -> DailyTripAssignment:
    base = _today_assignment_base()

    # Primary: driver listed on the active staff template
    assignment = base.filter(staff_template_id__driver_id=staff).first()

    # Alternative staff template (substitution active today)
    if assignment is None:
        assignment = base.filter(alt_staff_template_id__driver_id=staff).first()

    if not assignment:
        raise OperatorFlowError(
            "NO_ACTIVE_TRIP",
            "No trip is assigned to you for today.",
        )
    return assignment


def _is_driver_role(staff: Staffcreation) -> bool:
    role_obj = getattr(staff, "staffusertype_id", None)
    role_name = (getattr(role_obj, "name", "") or "").lower()
    return "driver" in role_name


def find_active_assignment_for_staff(staff: Staffcreation) -> DailyTripAssignment:
    """Resolve today's active trip for either a driver or an operator."""
    if _is_driver_role(staff):
        return find_active_assignment_for_driver(staff)
    return find_active_assignment_for_operator(staff)


# ---------------------------------------------------------------------------
# Bin QR resolution
# ---------------------------------------------------------------------------

def parse_bin_qr_payload(raw: str) -> str:
    """Extract the bin unique_id from a scanned QR value.

    Bins generate their QR via ``app.utils.bin_qr.generate_bin_qr_content`` which
    encodes ``{"id": "<bin.unique_id>"}``. Mobile scanners hand us back that raw
    string. We also accept the bare unique_id for manual entry / testing.
    """
    if not raw:
        raise OperatorFlowError(
            "BIN_NOT_FOUND",
            "QR payload is empty.",
            http_status=404,
        )
    value = raw.strip()
    if value.startswith("{"):
        try:
            decoded = json.loads(value)
        except ValueError:
            raise OperatorFlowError(
                "BIN_NOT_FOUND",
                "QR payload is not valid JSON.",
                http_status=404,
            )
        bin_id = decoded.get("id") or decoded.get("unique_id") or decoded.get("bin_id")
        if not bin_id:
            raise OperatorFlowError(
                "BIN_NOT_FOUND",
                "QR payload missing bin id field.",
                http_status=404,
            )
        return str(bin_id).strip()
    return value


def resolve_bin_from_qr(bin_qr: str) -> Bins:
    bin_id = parse_bin_qr_payload(bin_qr)
    bin_obj = (
        Bins.objects
        .filter(unique_id=bin_id, is_deleted=False)
        .select_related(
            "collection_point_id",
            "collection_point_id__panchayat_id",
            "collection_point_id__ward_id",
            "wastetype_id",
        )
        .first()
    )
    if not bin_obj:
        raise OperatorFlowError(
            "BIN_NOT_FOUND",
            f"No bin found for QR id '{bin_id}'.",
            http_status=404,
        )
    return bin_obj


# ---------------------------------------------------------------------------
# Cross-validation between bin and active assignment
# ---------------------------------------------------------------------------

def validate_bin_against_assignment(
    bin_obj: Bins, assignment: DailyTripAssignment
) -> DailyTripCollectionPoint:
    if str(bin_obj.wastetype_id_id) != str(assignment.waste_type_id_id):
        bin_waste = getattr(bin_obj.wastetype_id, "waste_type_name", "unknown")
        trip_waste = getattr(assignment.waste_type_id, "waste_type_name", "unknown")
        raise OperatorFlowError(
            "WRONG_WASTE_TYPE",
            f"This bin is {bin_waste}; your trip collects {trip_waste}.",
        )

    cp = bin_obj.collection_point_id

    # panchayat XOR ward — either dimension must match
    bin_panchayat = getattr(cp, "panchayat_id_id", None)
    bin_ward = getattr(cp, "ward_id_id", None)
    trip_panchayat = assignment.panchayat_id_id
    trip_ward = assignment.ward_id_id

    panchayat_match = bool(
        trip_panchayat and bin_panchayat and str(bin_panchayat) == str(trip_panchayat)
    )
    ward_match = bool(
        trip_ward and bin_ward and str(bin_ward) == str(trip_ward)
    )
    if not (panchayat_match or ward_match):
        if trip_panchayat:
            msg = "This bin is outside your assigned panchayat."
        elif trip_ward:
            msg = "This bin is outside your assigned ward."
        else:
            msg = "This bin is outside your assigned service area."
        raise OperatorFlowError("WRONG_PANCHAYAT", msg)

    trip_cp = (
        DailyTripCollectionPoint.objects
        .filter(
            trip_assignment_id=assignment,
            collection_point_id=cp,
            is_deleted=False,
        )
        .select_related("collection_point_id", "bin_id")
        .first()
    )
    if not trip_cp:
        raise OperatorFlowError(
            "CP_NOT_IN_TRIP",
            "This collection point is not part of your trip.",
        )

    if trip_cp.is_collected:
        raise OperatorFlowError(
            "ALREADY_COLLECTED",
            "This collection point has already been marked collected.",
            http_status=409,
        )

    return trip_cp


def build_scan_context(bin_qr: str, operator: Staffcreation) -> ScanContext:
    assignment = find_active_assignment_for_operator(operator)
    bin_obj = resolve_bin_from_qr(bin_qr)
    trip_cp = validate_bin_against_assignment(bin_obj, assignment)
    return ScanContext(bin=bin_obj, assignment=assignment, trip_cp=trip_cp)


# ---------------------------------------------------------------------------
# Progress + serializers
# ---------------------------------------------------------------------------

def progress_payload(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(1 for c in children if c.is_collected)
    return {
        "collected": collected,
        "total": total,
        "completed": total > 0 and collected == total,
    }


def _bin_qr_url(bin_obj: Bins, request=None) -> str | None:
    """Returns an absolute URL to the bin's printed QR PNG (or None)."""
    qr = getattr(bin_obj, "bin_qr", None)
    try:
        url = qr.url if qr else None
    except (ValueError, AttributeError):
        url = None
    if not url:
        return None
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def serialize_bin_brief(bin_obj: Bins, request=None) -> dict:
    return {
        "unique_id": bin_obj.unique_id,
        "bin_name": bin_obj.bin_name,
        # Operators scan this string to identify the bin; it matches the QR payload `id`.
        "bin_qr": bin_obj.unique_id,
        "bin_qr_image_url": _bin_qr_url(bin_obj, request=request),
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


def serialize_area_brief(assignment: DailyTripAssignment) -> dict:
    """Always one and only one of panchayat / ward is set on an assignment."""
    panchayat = assignment.panchayat_id
    ward = assignment.ward_id
    if panchayat:
        return {
            "kind": "panchayat",
            "unique_id": panchayat.unique_id,
            "name": panchayat.panchayat_name,
        }
    if ward:
        return {
            "kind": "ward",
            "unique_id": ward.unique_id,
            "name": ward.ward_name,
        }
    return {"kind": None, "unique_id": None, "name": None}


def serialize_assignment_brief(assignment: DailyTripAssignment) -> dict:
    waste_type = assignment.waste_type_id
    vehicle = assignment.vehicle_id
    area = serialize_area_brief(assignment)
    panchayat = assignment.panchayat_id
    ward = assignment.ward_id
    return {
        "unique_id": assignment.unique_id,
        "status": assignment.status,
        "trip_date": assignment.trip_date.isoformat(),
        # Convenience copies for clients that key off one or the other.
        "panchayat": (
            {"unique_id": panchayat.unique_id, "name": panchayat.panchayat_name}
            if panchayat
            else None
        ),
        "ward": (
            {"unique_id": ward.unique_id, "name": ward.ward_name}
            if ward
            else None
        ),
        "area": area,
        "waste_type": {
            "unique_id": waste_type.unique_id,
            "name": waste_type.waste_type_name,
        },
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


def maybe_resolve_driver(assignment: DailyTripAssignment):
    """Resolve the driver Staffcreation, honouring alternative-template overrides."""
    template = (
        getattr(assignment, "alt_staff_template_id", None)
        or assignment.staff_template_id
    )
    return getattr(template, "driver_id", None) if template else None
