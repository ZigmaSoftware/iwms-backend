"""Supervisor/admin review of Re-Trip requests.

    GET  /api/v1/schedule-operations/retrip-requests/?status=Pending
    POST /api/v1/schedule-operations/retrip-requests/{id}/approve/
    POST /api/v1/schedule-operations/retrip-requests/{id}/reject/

`approve` is where the continuation trip is born — see
`app/services/retrip_service.approve_retrip`. For a bin trip the caller sends
`collection_point_ids` (the stops ticked); for a household trip every
remaining household carries over automatically.

Creation only ever happens via `app.services.retrip_service` (currently only
`proceed_to_next_trip`, called from `DailyTripAssignmentViewSet.proceed_next_trip`)
— create/update/destroy on this resource are disabled so nothing bypasses the
service's snapshot-building and notification logic.
"""

from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.schedule_masters.trip_retrip_request import TripRetripRequest
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.core_modules.daily_operations.trip_retrip_serializer import (
    TripRetripRequestSerializer,
)
from app.services import retrip_service
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class TripRetripRequestViewSet(CompanyScopedViewSet):
    queryset = (
        TripRetripRequest.objects.filter(is_deleted=False)
        .select_related(
            "company_id",
            "project_id",
            "assignment",
            "assignment__trip_plan_id",
            "assignment__vehicle_id",
            "assignment__panchayat_id",
            "requested_by",
            "reviewed_by",
            "new_assignment",
        )
        .order_by("-created_at")
    )
    serializer_class = TripRetripRequestSerializer
    lookup_field = "unique_id"
    filter_backends = [ModelFieldQueryFilter, ModelFieldSearchFilter, SerializerOrderingFilter]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        assignment = params.get("assignment_id") or params.get("assignment")
        if assignment:
            qs = qs.filter(assignment__unique_id=assignment)

        return qs

    # ── writes disabled — go through retrip_service instead ───────────

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use proceed-next-trip on the trip assignment to open a Re-Trip request."},
            status=http_status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Re-Trip requests are read-only; use approve/reject."},
            status=http_status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Re-Trip requests cannot be deleted."},
            status=http_status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, unique_id=None):
        retrip = self.get_object()
        if not retrip.is_pending:
            return Response(
                {"detail": f"This request was already {retrip.status.lower()}."},
                status=http_status.HTTP_409_CONFLICT,
            )

        raw_ids = request.data.get("collection_point_ids")
        collection_point_ids = None
        if raw_ids is not None:
            if not isinstance(raw_ids, (list, tuple)):
                return Response(
                    {"collection_point_ids": "Expected a list of stop ids."},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )
            collection_point_ids = [str(value) for value in raw_ids]

        reviewer = request.user if isinstance(request.user, Staffcreation) else None
        continuation = retrip_service.approve_retrip(
            retrip,
            reviewed_by=reviewer,
            collection_point_ids=collection_point_ids,
            remarks=request.data.get("remarks"),
        )

        retrip.refresh_from_db()
        return Response(
            {
                "request": TripRetripRequestSerializer(retrip, context={"request": request}).data,
                "new_assignment_id": continuation.unique_id,
            },
            status=http_status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, unique_id=None):
        retrip = self.get_object()
        if not retrip.is_pending:
            return Response(
                {"detail": f"This request was already {retrip.status.lower()}."},
                status=http_status.HTTP_409_CONFLICT,
            )

        reviewer = request.user if isinstance(request.user, Staffcreation) else None
        retrip_service.reject_retrip(
            retrip,
            reviewed_by=reviewer,
            remarks=request.data.get("remarks"),
        )

        retrip.refresh_from_db()
        return Response(
            TripRetripRequestSerializer(retrip, context={"request": request}).data,
            status=http_status.HTTP_200_OK,
        )
