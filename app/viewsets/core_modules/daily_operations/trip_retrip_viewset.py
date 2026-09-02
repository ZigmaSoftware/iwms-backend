"""Supervisor/admin review of Re-Trip requests.

    GET  /api/v1/schedule-operations/retrip-requests/?status=Pending
    GET  /api/v1/schedule-operations/retrip-requests/?mine=true
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

`mine=true` scopes to requests raised against a trip plan THIS supervisor
owns (`TripPlan.supervisor_id == requester`) — the same identity-based
scoping `DailyTripAssignmentViewSet` uses. This matters because a supervisor
can supervise a trip plan outside their own home project/company (the
seed data has exactly this: a plan supervised cross-project); the base
`CompanyScopedViewSet.filter_queryset` would otherwise silently filter those
back out by re-narrowing to the requester's own project, undoing the `mine`
scoping.

`filter_queryset` is overridden to skip that home-project narrowing for
`mine=true` list requests AND for the detail routes (retrieve/approve/
reject) — a client only ever reaches those with an id it already saw via a
`mine=true` list, so home-project match is the wrong ownership check there
too. `_check_retrip_ownership()` does the real check for those three
actions instead (same trip-plan-supervisor identity, or platform
superadmin).
"""

from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from app.models.schedule_masters.trip_retrip_request import TripRetripRequest
from app.models.staff_creations.staffcreation import Staffcreation
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

        mine = params.get("mine")
        if mine and str(mine).lower() in ("1", "true", "yes"):
            # Supervisor app: requests raised against a trip plan this
            # supervisor owns — mirrors DailyTripAssignmentViewSet's
            # `mine=true`. See filter_queryset() below for why this must
            # also suppress the base class's home-project narrowing.
            qs = qs.filter(assignment__trip_plan_id__supervisor_id=self.request.user)

        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        assignment = params.get("assignment_id") or params.get("assignment")
        if assignment:
            qs = qs.filter(assignment__unique_id=assignment)

        return qs

    def filter_queryset(self, queryset):
        mine = self.request.query_params.get("mine")
        detail_route = self.action in ("retrieve", "approve", "reject")
        if detail_route or (mine and str(mine).lower() in ("1", "true", "yes")):
            # Two cases skip CompanyScopedViewSet's blind company/project
            # re-narrowing here:
            #   - `mine=true` (list): already scoped to trip plans the
            #     requester supervises, which can legitimately span
            #     projects/companies other than the requester's own home one.
            #   - a detail route (retrieve/approve/reject): the caller only
            #     ever reaches these with an id they already saw via a
            #     `mine=true` list, so home-project match is the wrong
            #     ownership check here too — `_check_retrip_ownership()`
            #     (called from approve/reject) does the real check instead.
            # Either way, re-narrowing by home project would silently 404 a
            # request that legitimately belongs to this supervisor. Run the
            # other configured filter backends (status/search/ordering)
            # without going through CompanyScopedViewSet.filter_queryset.
            for backend in list(self.filter_backends):
                queryset = backend().filter_queryset(self.request, queryset, self)
            return queryset
        return super().filter_queryset(queryset)

    def _check_retrip_ownership(self, retrip):
        """Approve/reject may only be decided by the trip plan's own
        supervisor (or a platform superadmin) — since `get_object()` for
        these detail routes deliberately skips the home-project filter
        above, this is the real authorization check for those two actions.
        """
        if self._is_platform_super_admin():
            return
        plan = getattr(retrip.assignment, "trip_plan_id", None)
        supervisor = getattr(plan, "supervisor_id", None) if plan else None
        if supervisor is None or supervisor.staff_unique_id != getattr(
            self.request.user, "staff_unique_id", None
        ):
            raise PermissionDenied("You do not supervise this trip plan.")

    def retrieve(self, request, *args, **kwargs):
        # filter_queryset() skips the home-project narrowing for this
        # action (see above), so enforce the real ownership check here
        # instead of relying on it. A superadmin still bypasses via
        # _check_retrip_ownership itself.
        retrip = self.get_object()
        self._check_retrip_ownership(retrip)
        serializer = self.get_serializer(retrip)
        return Response(serializer.data)

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
        self._check_retrip_ownership(retrip)
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
        self._check_retrip_ownership(retrip)
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
