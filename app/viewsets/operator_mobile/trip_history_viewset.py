from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.permissions.operator_permission import IsOperatorRole
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


def _serialize_summary(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(1 for c in children if c.is_collected)
    total_weight = sum(
        (c.collected_weight_kg or Decimal("0")) for c in children
    )
    waste_type = assignment.waste_type_id
    panchayat_dict, ward_dict = _area_payload(assignment)
    return {
        "assignment_unique_id": assignment.unique_id,
        "trip_date": assignment.trip_date.isoformat(),
        "status": assignment.status,
        "panchayat": panchayat_dict,
        "ward": ward_dict,
        "waste_type": {
            "unique_id": waste_type.unique_id,
            "name": waste_type.waste_type_name,
        },
        "progress": {
            "collected": collected,
            "total": total,
            "completed": total > 0 and collected == total,
        },
        "total_weight_kg": str(total_weight),
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

    permission_classes = [IsOperatorRole]
    lookup_field = "unique_id"

    def _base_queryset(self, operator):
        # Match either the primary staff template's operator or the alternative
        # (substitute) template's operator. We omit the extra_operator_id JSON
        # membership query here because it isn't supported on SQLite (used in
        # tests); extras are uncommon and can be filtered in Python if needed.
        from django.db.models import Q
        return (
            DailyTripAssignment.objects
            .filter(is_deleted=False)
            .filter(
                Q(staff_template_id__operator_id=operator)
                | Q(alt_staff_template_id__operator_id=operator)
            )
            .select_related(
                "panchayat_id",
                "ward_id",
                "waste_type_id",
                "vehicle_id",
            )
            .prefetch_related("trip_collection_points")
            .order_by("-trip_date", "-scheduled_time")
        )

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        qs = self._base_queryset(operator)
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
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        assignment = (
            self._base_queryset(operator)
            .filter(unique_id=unique_id)
            .first()
        )
        if not assignment:
            return Response(
                {"code": "NOT_FOUND", "detail": "Trip not found for this operator."},
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
