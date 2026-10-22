"""Supervisor/admin review of Re-Trip requests.

    GET  /api/v1/schedule-operations/retrip-requests/?status=Pending
    GET  /api/v1/schedule-operations/retrip-requests/?mine=true
    GET  /api/v1/schedule-operations/retrip-requests/pending-stops/?assignment_id=…
    GET  /api/v1/schedule-operations/retrip-requests/reason-codes/
    POST /api/v1/schedule-operations/retrip-requests/   {assignment_id, reason_code, reason}
    POST /api/v1/schedule-operations/retrip-requests/{id}/approve/
    POST /api/v1/schedule-operations/retrip-requests/{id}/reject/

`approve` is where the continuation trip is born — see
`app/services/retrip_service.approve_retrip`. For a bin trip the caller sends
`collection_point_ids` (the stops ticked); for a household trip every
remaining household carries over automatically.

Creation only ever happens via `app.services.retrip_service` — the driver
app's `trip-lifecycle/{id}/end/`, the web one-step `proceed-next-trip`, or
`create` below (the web form raising a Pending request on a driver's behalf).
`create` is overridden to call `request_retrip` rather than the serializer,
and update/destroy are disabled, so nothing bypasses the service's
snapshot-building and notification logic.

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
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.core_modules.daily_operations.trip_retrip_serializer import (
    TripRetripRequestSerializer,
)
from app.services import retrip_service
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import ActionAuditMixin


class TripRetripRequestViewSet(ActionAuditMixin, CompanyScopedViewSet):
    queryset = (
        TripRetripRequest.objects.filter(is_deleted=False)
        .order_by("-created_at")
    )
    serializer_class = TripRetripRequestSerializer
    lookup_field = "unique_id"
    filter_backends = [ModelFieldQueryFilter, ModelFieldSearchFilter, SerializerOrderingFilter]

    @staticmethod
    def permission_action_for_request(request, default_action):
        path = request.path.rstrip("/")
        if path.endswith("/approve") or path.endswith("/reject"):
            return "edit"
        return default_action

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        mine = params.get("mine")
        if mine and str(mine).lower() in ("1", "true", "yes"):
            # Supervisor app: requests raised against a trip plan this
            # supervisor owns — mirrors DailyTripAssignmentViewSet's
            # `mine=true`. See filter_queryset() below for why this must
            # also suppress the base class's home-project narrowing.
            from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan

            supervised_plan_ids = TripPlan.objects.filter(
                supervisor_id=self.request.user.staff_unique_id,
            ).values("unique_id")
            matching_assignment_ids = DailyTripAssignment.objects.filter(
                trip_plan_id__in=supervised_plan_ids
            ).values_list("unique_id", flat=True)
            qs = qs.filter(assignment_id__in=matching_assignment_ids)

        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        assignment = params.get("assignment_id") or params.get("assignment")
        if assignment:
            qs = qs.filter(assignment_id=assignment)

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

        The role-level `edit` grant only reaches requests inside the caller's
        own company/project: the home-project filter is skipped for these
        routes, so without that check anyone holding `edit` in one company
        could decide another company's requests by id.
        """
        if self._is_platform_super_admin():
            return
        assignment = retrip.assignment
        plan_id = getattr(assignment, "trip_plan_id", None) if assignment else None
        plan = TripPlan.objects.filter(unique_id=plan_id).first() if plan_id else None
        supervisor = getattr(plan, "supervisor_id", None) if plan else None
        if supervisor is not None and str(supervisor) == str(getattr(
            self.request.user, "staff_unique_id", None
        )):
            return
        permissions = getattr(self.request, "resolved_permissions", {}) or {}
        retrip_actions = (
            permissions
            .get("schedule-operations", {})
            .get("retrip-requests", [])
        )
        if "edit" in retrip_actions and self._scope_to_tenant(
            TripRetripRequest.objects.filter(pk=retrip.pk)
        ).exists():
            return
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

    # ── web form: raise a request on a driver's behalf ────────────────

    def _resolve_open_assignment(self, assignment_id):
        """The trip, scoped to the caller's company/project, still open."""
        if not assignment_id:
            raise ValidationError({"assignment_id": "Select a trip."})
        assignment = (
            self._scope_to_tenant(
                DailyTripAssignment.objects.filter(is_deleted=False)
            )
            .filter(unique_id=assignment_id)
            .first()
        )
        if assignment is None:
            raise NotFound("Trip not found.")
        if assignment.status in (
            DailyTripAssignment.STATUS_COMPLETED,
            DailyTripAssignment.STATUS_CANCELLED,
        ):
            raise ValidationError({"assignment_id": "This trip is already closed."})
        return assignment

    @action(detail=False, methods=["get"], url_path="reason-codes")
    def reason_codes(self, request):
        """The reason categories a request can be raised with."""
        return Response(retrip_service.reason_code_options())

    @action(detail=False, methods=["get"], url_path="pending-stops")
    def pending_stops(self, request):
        """What a request raised now would carry — previewed by the web form."""
        assignment = self._resolve_open_assignment(
            request.query_params.get("assignment_id")
        )
        return Response(retrip_service.build_pending_snapshot(assignment))

    def create(self, request, *args, **kwargs):
        """Web counterpart of the driver app's `trip-lifecycle/{id}/end/` —
        same rules (open trip, stops left, mandatory reason, one pending
        request per trip), same `request_retrip` service, so the supervisor
        reviews it exactly like a driver-raised one.
        """
        assignment = self._resolve_open_assignment(
            str(request.data.get("assignment_id") or "").strip()
        )

        existing = TripRetripRequest.objects.filter(
            assignment_id=assignment.unique_id,
            status=TripRetripRequest.STATUS_PENDING,
            is_deleted=False,
        ).first()
        if existing is not None:
            retrip_service.expire_retrip_if_due(existing)
            existing.refresh_from_db()
            if existing.is_pending:
                return Response(
                    {"detail": "A Re-Trip request for this trip is already awaiting approval."},
                    status=http_status.HTTP_409_CONFLICT,
                )

        if (
            not assignment.pending_bin_stops().exists()
            and not assignment.pending_household_stops().exists()
        ):
            return Response(
                {"detail": "This trip has no pending stops left to carry over."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        requester = request.user if isinstance(request.user, Staffcreation) else None
        try:
            retrip = retrip_service.request_retrip(
                assignment,
                requested_by=requester,
                reason=request.data.get("reason"),
                reason_code=request.data.get("reason_code"),
            )
        except retrip_service.RetripReasonInvalid as exc:
            return Response({"reason": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        except retrip_service.RetripAlreadyPending as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_409_CONFLICT)
        except retrip_service.RetripNotAllowed as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        return Response(
            TripRetripRequestSerializer(retrip, context={"request": request}).data,
            status=http_status.HTTP_201_CREATED,
        )

    # ── edits disabled — decide via approve/reject ────────────────────

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
        try:
            continuation = retrip_service.approve_retrip(
                retrip,
                reviewed_by=reviewer,
                collection_point_ids=collection_point_ids,
                remarks=request.data.get("remarks"),
            )
        except retrip_service.RetripRequestUnavailable as exc:
            return Response(
                {"detail": str(exc)}, status=http_status.HTTP_409_CONFLICT
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST
            )
        if continuation is None:
            return Response(
                {"detail": "This request expired before it could be approved."},
                status=http_status.HTTP_409_CONFLICT,
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
        try:
            decided = retrip_service.reject_retrip(
                retrip,
                reviewed_by=reviewer,
                remarks=request.data.get("remarks"),
            )
        except retrip_service.RetripRequestUnavailable as exc:
            return Response(
                {"detail": str(exc)}, status=http_status.HTTP_409_CONFLICT
            )
        if decided.status == TripRetripRequest.STATUS_EXPIRED:
            return Response(
                {"detail": "This request expired before it could be rejected."},
                status=http_status.HTTP_409_CONFLICT,
            )

        retrip.refresh_from_db()
        return Response(
            TripRetripRequestSerializer(retrip, context={"request": request}).data,
            status=http_status.HTTP_200_OK,
        )
