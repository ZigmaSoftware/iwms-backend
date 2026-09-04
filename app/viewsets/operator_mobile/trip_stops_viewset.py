"""Paginated stop fetching for a trip already open on the driver's home page.

`my-trip-today`/`my-trips-today` only ever embed the FIRST page (20) of a
trip's bin/household stops (see `STOPS_PAGE_SIZE` in trip_today_serializer.py)
— a trip with hundreds of stops used to re-serialize and re-transmit the
whole list on every single scan/collect, every pull-to-refresh, and every app
resume, since those all re-hit the trip-today endpoints. This viewset is
where the REST of a trip's stops come from, fetched only as the driver
actually scrolls to them.
"""

from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.trip_today_serializer import (
    HouseholdCollectionSerializer,
    STOPS_PAGE_SIZE,
    TripCollectionPointSerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    _staff_owns_assignment,
    resolve_operator_staff,
)

STOP_TYPES = {
    "bin": (
        "trip_collection_points",
        DailyTripCollectionPoint,
        TripCollectionPointSerializer,
        ("collection_point_id", "bin_id"),
    ),
    "household": (
        "trip_household_collections",
        DailyTripHouseholdCollection,
        HouseholdCollectionSerializer,
        ("customer_id", "customer_id__city"),
    ),
}


class TripStopsViewSet(viewsets.ViewSet):
    """GET /api/v1/operator-mobile/trip-stops/

    Query params: `assignment_id` (required), `type` ("bin" or "household",
    required), `page` (1-based, default 1). Always PAGE_SIZE=20 — this is a
    driver-app scroll-loading endpoint, not a general list view, so there is
    no reason to let a caller ask for an arbitrary page size the way an admin
    DataTable would.
    """

    permission_classes = [IsOperatorRole]

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message}, status=exc.http_status
            )

        assignment_id = (request.query_params.get("assignment_id") or "").strip()
        stop_type = (request.query_params.get("type") or "").strip().lower()
        if not assignment_id:
            return Response(
                {"code": "ASSIGNMENT_ID_REQUIRED", "detail": "assignment_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if stop_type not in STOP_TYPES:
            return Response(
                {
                    "code": "INVALID_TYPE",
                    "detail": "type must be 'bin' or 'household'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            page = max(1, int(request.query_params.get("page") or 1))
        except ValueError:
            page = 1

        assignment = DailyTripAssignment.objects.filter(
            unique_id=assignment_id, is_deleted=False
        ).first()
        if assignment is None:
            return Response(
                {"code": "ASSIGNMENT_NOT_FOUND", "detail": "Trip not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Ownership check — a driver must not be able to page through another
        # crew's trip just by guessing/replaying an assignment id.
        if not _staff_owns_assignment(assignment, operator):
            return Response(
                {"code": "TRIP_NOT_YOURS", "detail": "This trip is not assigned to you."},
                status=status.HTTP_403_FORBIDDEN,
            )

        related_name, _model, serializer_cls, select_related = STOP_TYPES[stop_type]
        queryset = (
            getattr(assignment, related_name)
            .filter(is_deleted=False)
            .select_related(*select_related)
            .order_by("sequence")
        )

        count = queryset.count()
        start = (page - 1) * STOPS_PAGE_SIZE
        end = start + STOPS_PAGE_SIZE
        page_items = queryset[start:end]

        return Response({
            "count": count,
            "page": page,
            "page_size": STOPS_PAGE_SIZE,
            "has_next": end < count,
            "results": serializer_cls(page_items, many=True).data,
        })
