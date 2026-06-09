from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.permissions.operator_permission import IsOperatorOrDriverRole
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    resolve_operator_staff,
)


def _area_payload(assignment: DailyTripAssignment) -> tuple:
    """Return (panchayat_dict_or_none, ward_dict_or_none)."""
    panchayat = assignment.panchayat_id
    ward = assignment.ward_id
    panchayat_dict = (
        {"unique_id": panchayat.unique_id, "name": panchayat.panchayat_name}
        if panchayat
        else None
    )
    ward_dict = (
        {"unique_id": ward.unique_id, "name": ward.ward_name}
        if ward
        else None
    )
    return panchayat_dict, ward_dict


def _vehicle_payload(assignment: DailyTripAssignment) -> dict | None:
    vehicle = assignment.vehicle_id or getattr(
        assignment.trip_plan_id, "vehicle_id", None
    )
    if not vehicle:
        return None
    return {
        "unique_id": vehicle.unique_id,
        "vehicle_no": vehicle.vehicle_no,
        "capacity": str(vehicle.capacity) if vehicle.capacity is not None else None,
    }


def _staff_brief(staff) -> dict | None:
    if not staff:
        return None
    return {
        "unique_id": staff.staff_unique_id,
        "username": getattr(staff, "username", None),
        "name": getattr(staff, "employee_name", None),
        "phone": getattr(staff, "phone_number", None) or getattr(staff, "mobile", None),
    }


def _staff_payload(assignment: DailyTripAssignment) -> dict:
    """Operator / driver names, honouring alt-template substitutions."""
    template = assignment.staff_template_id
    alt = assignment.alt_staff_template_id
    effective = alt or template

    return {
        "driver": _staff_brief(getattr(effective, "driver_id", None)),
        "operator": _staff_brief(getattr(effective, "operator_id", None)),
        "is_alt_active": alt is not None,
        "template_code": getattr(template, "display_code", None) if template else None,
        "alt_template_code": getattr(alt, "display_code", None) if alt else None,
    }


def _serialize_summary(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(1 for c in children if c.is_collected)
    total_weight = sum(
        (c.collected_weight_kg or Decimal("0")) for c in children
    )
    waste_type = assignment.waste_type_id
    panchayat_dict, ward_dict = _area_payload(assignment)
    trip_plan = assignment.trip_plan_id
    return {
        "assignment_unique_id": assignment.unique_id,
        "trip_date": assignment.trip_date.isoformat(),
        "status": assignment.status,
        "approval_status": assignment.approval_status,
        "scheduled_time": (
            assignment.scheduled_time.isoformat()
            if assignment.scheduled_time
            else None
        ),
        "actual_start_time": (
            assignment.actual_start_time.isoformat()
            if assignment.actual_start_time
            else None
        ),
        "actual_end_time": (
            assignment.actual_end_time.isoformat()
            if assignment.actual_end_time
            else None
        ),
        "panchayat": panchayat_dict,
        "ward": ward_dict,
        "waste_type": {
            "unique_id": waste_type.unique_id,
            "name": waste_type.waste_type_name,
        },
        "vehicle": _vehicle_payload(assignment),
        "staff": _staff_payload(assignment),
        "trip_plan": (
            {
                "unique_id": trip_plan.unique_id,
                "display_code": trip_plan.display_code,
            }
            if trip_plan
            else None
        ),
        "progress": {
            "collected": collected,
            "total": total,
            "completed": total > 0 and collected == total,
        },
        "total_weight_kg": str(total_weight),
        "remarks": assignment.remarks,
    }


def _serialize_event(event: BinCollectionEvent) -> dict:
    # The new BinCollectionEvent has no scanned_qr / event_at / latitude /
    # longitude columns. We surface created_at as event_at for backwards
    # compatibility with the mobile model.
    return {
        "unique_id": event.unique_id,
        "event_at": event.created_at.isoformat(),
        "collected_weight_kg": str(event.collected_weight_kg),
        "scanned_qr": event.bin_id_id,
        "bin": {
            "unique_id": event.bin_id_id,
            "bin_name": getattr(event.bin_id, "bin_name", None),
        },
        "collection_point": {
            "unique_id": event.collection_point_id_id,
            "name": getattr(event.collection_point_id, "cp_name", None),
        },
        "latitude": (
            str(event.driver_latitude) if event.driver_latitude is not None else None
        ),
        "longitude": (
            str(event.driver_longitude) if event.driver_longitude is not None else None
        ),
        "notes": event.notes,
    }


class TripHistoryViewSet(viewsets.ViewSet):
    """
    GET /api/v1/operator-mobile/trip-history/            (list)
    GET /api/v1/operator-mobile/trip-history/{trip_id}/  (detail)
    """

    permission_classes = [IsOperatorOrDriverRole]
    lookup_field = "unique_id"

    def _base_queryset(self, staff):
        # Match the authenticated staff member against the effective staff
        # template. Operators and drivers see the same DailyTripAssignment and
        # DailyTripCollectionPoint rows, so collection status stays centralized.
        from django.db.models import Q

        role_obj = getattr(staff, "staffusertype_id", None)
        role_name = (getattr(role_obj, "name", "") or "").lower()
        if "driver" in role_name:
            staff_filter = (
                Q(staff_template_id__driver_id=staff)
                | Q(alt_staff_template_id__driver_id=staff)
            )
        else:
            staff_filter = (
                Q(staff_template_id__operator_id=staff)
                | Q(alt_staff_template_id__operator_id=staff)
            )

        return (
            DailyTripAssignment.objects
            .filter(is_deleted=False)
            .filter(staff_filter)
            .select_related(
                "panchayat_id",
                "ward_id",
                "waste_type_id",
                "vehicle_id",
                "trip_plan_id",
                "trip_plan_id__vehicle_id",
                "staff_template_id",
                "staff_template_id__driver_id",
                "staff_template_id__operator_id",
                "alt_staff_template_id",
                "alt_staff_template_id__driver_id",
                "alt_staff_template_id__operator_id",
            )
            .prefetch_related("trip_collection_points")
            .order_by("-trip_date", "-scheduled_time")
        )

    def list(self, request):
        try:
            staff = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        qs = self._base_queryset(staff)
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        if date_from:
            qs = qs.filter(trip_date__gte=date_from)
        if date_to:
            qs = qs.filter(trip_date__lte=date_to)

        results = [_serialize_summary(a) for a in qs[:200]]
        return Response({"results": results}, status=status.HTTP_200_OK)

    def retrieve(self, request, unique_id=None):
        try:
            staff = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        assignment = (
            self._base_queryset(staff)
            .filter(unique_id=unique_id)
            .first()
        )
        if not assignment:
            return Response(
                {"code": "NOT_FOUND", "detail": "Trip not found for this staff member."},
                status=status.HTTP_404_NOT_FOUND,
            )

        summary = _serialize_summary(assignment)
        events_qs = (
            BinCollectionEvent.objects
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .select_related("bin_id", "collection_point_id")
            .order_by("created_at")
        )
        summary["events"] = [_serialize_event(e) for e in events_qs]

        cps = (
            assignment.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id", "bin_id")
            .order_by("sequence")
        )
        def _bin_qr_url(bin_obj):
            try:
                return bin_obj.bin_qr.url if bin_obj.bin_qr else None
            except (ValueError, AttributeError):
                return None

        summary["collection_points"] = [
            {
                "unique_id": cp.unique_id,
                "sequence": cp.sequence,
                "is_collected": cp.is_collected,
                "status": cp.status,
                "collected_at": cp.collected_at.isoformat() if cp.collected_at else None,
                "collected_weight_kg": (
                    str(cp.collected_weight_kg) if cp.collected_weight_kg is not None else None
                ),
                "collection_point": {
                    "unique_id": cp.collection_point_id.unique_id,
                    "name": cp.collection_point_id.cp_name,
                    "latitude": (
                        str(cp.collection_point_id.latitude)
                        if cp.collection_point_id.latitude is not None
                        else None
                    ),
                    "longitude": (
                        str(cp.collection_point_id.longitude)
                        if cp.collection_point_id.longitude is not None
                        else None
                    ),
                },
                "bin": {
                    "unique_id": cp.bin_id.unique_id,
                    "bin_name": cp.bin_id.bin_name,
                    # Match the new contract: bin_qr = bin.unique_id; image is separate.
                    "bin_qr": cp.bin_id.unique_id,
                    "bin_qr_image_url": (
                        request.build_absolute_uri(_bin_qr_url(cp.bin_id))
                        if _bin_qr_url(cp.bin_id)
                        else None
                    ),
                },
            }
            for cp in cps
        ]

        return Response(summary, status=status.HTTP_200_OK)
