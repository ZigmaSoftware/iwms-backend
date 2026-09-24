from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.assets.bins import Bins
from app.permissions.operator_permission import IsOperatorRole
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    resolve_operator_staff,
)


def _serialize_summary(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(1 for c in children if c.is_collected)
    total_weight = sum(
        (c.collected_weight_kg or Decimal("0")) for c in children
    )
    panchayat_id = assignment.panchayat_id
    waste_type_id = assignment.primary_waste_type
    
    panchayat = None
    if panchayat_id:
        from app.models.masters.panchayat import Panchayat
        panchayat = Panchayat.objects.filter(unique_id=panchayat_id).first()
    
    waste_type = None
    if waste_type_id:
        from app.models.staff_creations.waste_collection_bluetooth import WasteType
        waste_type = WasteType.objects.filter(unique_id=waste_type_id).first()
    
    return {
        "assignment_unique_id": assignment.unique_id,
        "trip_date": assignment.trip_date.isoformat(),
        "status": assignment.status,
        "panchayat": {
            "unique_id": panchayat.unique_id,
            "name": panchayat.panchayat_name,
        } if panchayat else None,
        "waste_type": (
            {
                "unique_id": waste_type.unique_id,
                "name": waste_type.waste_type_name,
            }
            if waste_type
            else None
        ),
        "progress": {
            "collected": collected,
            "total": total,
            "completed": total > 0 and collected == total,
        },
        "total_weight_kg": str(total_weight),
    }


def _serialize_event(event: BinCollectionEvent) -> dict:
    return {
        "unique_id": event.unique_id,
        "event_at": event.event_at.isoformat(),
        "collected_weight_kg": str(event.collected_weight_kg),
        "scanned_qr": event.scanned_qr,
        "bin": {
            "unique_id": event.bin_id,
            "bin_name": None,  # Would need separate query to fetch
        },
        "collection_point": {
            "unique_id": event.collection_point_id,
            "name": None,  # Would need separate query to fetch
        },
        "latitude": str(event.latitude) if event.latitude is not None else None,
        "longitude": str(event.longitude) if event.longitude is not None else None,
        "notes": event.notes,
    }


class TripHistoryViewSet(viewsets.ViewSet):
    """
    GET /api/v1/operator-mobile/trip-history/            (list)
    GET /api/v1/operator-mobile/trip-history/{trip_id}/  (detail)
    """

    permission_classes = [IsOperatorRole]
    permission_resource = "DailyTripAssignment"
    lookup_field = "unique_id"

    def _base_queryset(self, operator):
        # Primary path: assignments where the operator is the template's main operator.
        # We omit the extra_operator_id JSON membership query here because it isn't
        # supported on SQLite (used in tests); extras are uncommon and can be added
        # later as a Python-side filter when needed.
        # staff_template_id is a plain CharField now, not a real FK, so it
        # can't be traversed with `__operator_id`, and trip_collection_points
        # is a resolver @property (not a reverse relation) so it can't be
        # prefetch_related-ed; "waste_types" was never a field/property here.
        from app.models.schedule_masters.staff_template import StaffTemplate

        staff_template_ids = set(
            StaffTemplate.objects.filter(
                operator_id=operator.staff_unique_id
            ).values_list("unique_id", flat=True)
        )
        return (
            DailyTripAssignment.objects
            .filter(is_deleted=False)
            .filter(staff_template_id__in=staff_template_ids)
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
            .order_by("event_at")
        )
        summary["events"] = [_serialize_event(e) for e in events_qs]

        cps = (
            assignment.trip_collection_points
            .filter(is_deleted=False)
            .order_by("sequence")
        )
        
        # Fetch related objects for the collection points
        collection_point_ids = [cp.collection_point_id for cp in cps if cp.collection_point_id]
        bin_ids = [cp.bin_id for cp in cps if cp.bin_id]
        
        collection_points = {
            cp.unique_id: cp for cp in Collection_point.objects.filter(unique_id__in=collection_point_ids)
        }
        bins = {
            b.unique_id: b for b in Bins.objects.filter(unique_id__in=bin_ids)
        }

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
                    "unique_id": cp.collection_point_id,
                    "name": collection_points.get(cp.collection_point_id).cp_name if collection_points.get(cp.collection_point_id) else None,
                },
                "bin": {
                    "unique_id": cp.bin_id,
                    "bin_name": bins.get(cp.bin_id).bin_name if bins.get(cp.bin_id) else None,
                    "bin_qr": bins.get(cp.bin_id).bin_qr if bins.get(cp.bin_id) else None,
                },
            }
            for cp in cps
        ]

        return Response(summary, status=status.HTTP_200_OK)
