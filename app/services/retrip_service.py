"""Re-Trip: close a trip that still has stops, and carry the rest to a new one.

Ported from the government app's `retrip_service.py`, adapted for private's
company/project tenancy: `TripRetripRequest` carries its own `company_id`/
`project_id` (mirroring `VehicleBreakdown`), and the continuation assignment
inherits them from the source assignment automatically via
`DailyTripAssignment.save()` / `CompanyScopedViewSet`.

Carry-over rules differ by collection type:
  * household — the supervisor/admin can pick which household stops move.
  * bin       — the supervisor/admin can pick which collection points move.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.staff_notification_service import notify_staff
from app.utils.related_prefetch import prefetch_related_rows, related
from app.services.retrip_timeout_service import (
    deadline_for,
    expire_retrip_if_due,
    timeout_minutes,
)


class RetripRequestUnavailable(ValueError):
    pass


class RetripAlreadyPending(RetripRequestUnavailable):
    """The trip already has a live Pending request; `.request` is that one."""

    def __init__(self, request):
        super().__init__("A Re-Trip request for this trip is already awaiting approval.")
        self.request = request


class RetripNotAllowed(ValueError):
    """The trip is in a state a Re-Trip cannot start from."""


class RetripReasonInvalid(ValueError):
    """The reason code / text does not meet the reason rules."""


def reason_code_options():
    """The reason categories, for clients to render a picker."""
    return [
        {"value": value, "label": label}
        for value, label in TripRetripRequest.REASON_CODE_CHOICES
    ]


def resolve_reason(reason_code, note):
    """Validate a reason and return `(reason_code, reason_text)`.

    A listed category needs no further words — the text becomes its label,
    plus the note when one is given. "Other" must be described in at least
    `OTHER_REASON_MIN_LENGTH` characters. A caller that sends no code (an
    older driver app with only a free-text box) is treated as "Other", so
    its text has to meet the same bar.
    """
    code = str(reason_code or "").strip().upper() or TripRetripRequest.REASON_OTHER
    note = str(note or "").strip()
    labels = dict(TripRetripRequest.REASON_CODE_CHOICES)
    if code not in labels:
        raise RetripReasonInvalid("Choose a valid reason.")
    if code == TripRetripRequest.REASON_OTHER:
        minimum = TripRetripRequest.OTHER_REASON_MIN_LENGTH
        if len(note) < minimum:
            raise RetripReasonInvalid(
                f"Describe the reason in at least {minimum} characters."
            )
        return code, note
    return code, f"{labels[code]}: {note}" if note else labels[code]


_CLOSED_STATUSES = (
    DailyTripAssignment.STATUS_COMPLETED,
    DailyTripAssignment.STATUS_CANCELLED,
)

UNSELECTED_STOP_REASON = "Not carried over in {source}: left out of the next trip."


def _lock_assignment(assignment_or_id):
    """Re-read the trip under a row lock.

    Lock order everywhere in the Re-Trip flow is trip -> request -> stops
    (the scan paths take trip -> stop), so concurrent callers queue on the
    trip row instead of deadlocking. Returns None if the trip is gone.
    """
    assignment_id = getattr(assignment_or_id, "unique_id", assignment_or_id)
    return (
        DailyTripAssignment.objects.select_for_update()
        .filter(unique_id=assignment_id)
        .first()
    )


def _live_pending_request(assignment):
    """The trip's Pending request that is still inside its window, or None.

    A locking read, so it sees a request another transaction just committed
    even under MySQL's REPEATABLE READ snapshot. Overdue ones are expired on
    the way past.
    """
    pending = TripRetripRequest.objects.select_for_update().filter(
        assignment_id=assignment.unique_id,
        status=TripRetripRequest.STATUS_PENDING,
        is_deleted=False,
    )
    for request in pending:
        if not expire_retrip_if_due(request):
            return request
    return None


def _supersede_pending_requests(source, *, reviewed_by, continuation, reason):
    """Close every other Pending request on `source` once it has been closed
    some other way — left Pending, one could later be approved and copy the
    same stops into a second continuation."""
    for request in TripRetripRequest.objects.select_for_update().filter(
        assignment_id=source.unique_id,
        status=TripRetripRequest.STATUS_PENDING,
        is_deleted=False,
    ):
        request.mark_reviewed(
            status=TripRetripRequest.STATUS_REJECTED,
            by=reviewed_by,
            remarks=f"Superseded: {reason} ({continuation.unique_id}).",
        )


def _close_unselected_stops(source, *, bins, households, reason):
    """Mark stops the reviewer chose NOT to carry over as Missed.

    The source trip is about to be closed, so a stop left Pending on it would
    be stranded: never collected, never missed, invisible to the end-of-day
    closer. Customers who said "I'm home now" get a Missed Pickup ticket,
    same as every other path that ends their stop Not Available.
    """
    now = timezone.now()
    if bins:
        DailyTripCollectionPoint.objects.filter(
            unique_id__in=[stop.unique_id for stop in bins]
        ).update(
            status=DailyTripCollectionPoint.STATUS_MISSED,
            status_reason=reason,
            is_collected=False,
            updated_at=now,
        )
    if households:
        DailyTripHouseholdCollection.objects.filter(
            unique_id__in=[stop.unique_id for stop in households]
        ).update(
            status=DailyTripHouseholdCollection.STATUS_MISSED,
            status_reason=reason,
            is_collected=False,
            updated_at=now,
        )
        flagged = [stop.unique_id for stop in households if stop.customer_available_at]
        if flagged:
            from app.services.customer_availability import raise_missed_pickup_ticket

            for stop in DailyTripHouseholdCollection.objects.filter(unique_id__in=flagged):
                raise_missed_pickup_ticket(stop)


def build_pending_snapshot(assignment):
    """What is still outstanding, in a shape the supervisor screen can render."""
    return build_pending_snapshots([assignment])[assignment.unique_id]


def build_pending_snapshots(assignments):
    """`build_pending_snapshot` for many trips at once, with their pending
    stops and the stops' collection points / customers read in one query per
    table: {assignment unique_id: snapshot}."""
    from app.models.core_modules.schedule_setup.collection_point import Collection_point
    from app.models.masters.customer_masters.customercreation import CustomerCreation

    ids = [a.unique_id for a in assignments if a is not None]
    snapshots = {uid: {"collection_points": [], "households": []} for uid in ids}
    if not ids:
        return snapshots
    # Each model's Meta ordering keeps every trip's stops in sequence order.
    bins = list(DailyTripAssignment.pending_stops(
        DailyTripCollectionPoint.objects.filter(trip_assignment_id__in=ids)
    ))
    households = list(DailyTripAssignment.pending_stops(
        DailyTripHouseholdCollection.objects.filter(trip_assignment_id__in=ids)
    ))
    prefetch_related_rows(bins, {"collection_point": (Collection_point, "collection_point_id")})
    prefetch_related_rows(households, {"customer": (CustomerCreation, "customer_id")})
    for stop in bins:
        snapshots[stop.trip_assignment_id]["collection_points"].append({
            "unique_id": stop.unique_id,
            "sequence": stop.sequence,
            "status": stop.status,
            "collection_point_id": stop.collection_point_id,
            "name": getattr(related(stop, "collection_point"), "cp_name", None),
            "bin_id": stop.bin_id,
        })
    for stop in households:
        snapshots[stop.trip_assignment_id]["households"].append({
            "unique_id": stop.unique_id,
            "sequence": stop.sequence,
            "status": stop.status,
            "customer_id": stop.customer_id,
            "name": getattr(related(stop, "customer"), "customer_name", None),
        })
    return snapshots


def _crew_of(assignment):
    """Driver + operator on the effective (possibly substituted) template."""
    # *_id columns are plain id strings — resolve rows via the properties.
    template = assignment.alt_staff_template or assignment.staff_template
    if template is None:
        return []
    return [
        staff
        for staff in (template.driver, template.operator)
        if staff is not None
    ]


def _supervisors_for(assignment):
    """Who should be asked to approve — the trip plan's assigned supervisor."""
    plan = assignment.trip_plan
    supervisor = plan.supervisor if plan else None
    return [supervisor] if supervisor is not None else []


@transaction.atomic
def request_retrip(assignment, *, requested_by, reason, reason_code=None):
    """Ask to close `assignment` early. Trip stays In Progress.

    `reason_code`/`reason` follow `resolve_reason` (raises
    `RetripReasonInvalid`). Only a running trip qualifies: cutting short one
    that never started would close it as a zero-duration "Completed" trip
    and hand all of its work to a new one. At most one Pending request per
    trip — enforced here under the trip's row lock, not a DB constraint,
    because MySQL ignores conditional unique constraints.
    """
    reason_code, reason = resolve_reason(reason_code, reason)
    assignment = _lock_assignment(assignment)
    if assignment is None or assignment.status in _CLOSED_STATUSES:
        raise RetripNotAllowed("This trip is already closed.")
    if assignment.status != DailyTripAssignment.STATUS_IN_PROGRESS:
        raise RetripNotAllowed(
            "This trip has not started yet, so it cannot be cut short."
        )
    existing = _live_pending_request(assignment)
    if existing is not None:
        raise RetripAlreadyPending(existing)

    snapshot = build_pending_snapshot(assignment)

    request = TripRetripRequest.objects.create(
        company_id=assignment.company_id,
        project_id=assignment.project_id,
        assignment_id=assignment.unique_id,
        requested_by_id=getattr(requested_by, "staff_unique_id", None),
        reason_code=reason_code,
        reason=reason,
        pending_bin_count=len(snapshot["collection_points"]),
        pending_household_count=len(snapshot["households"]),
        pending_snapshot=snapshot,
        expires_at=timezone.now() + timedelta(minutes=timeout_minutes()),
    )

    pending_total = request.pending_bin_count + request.pending_household_count
    for supervisor in _supervisors_for(assignment):
        notify_staff(
            supervisor,
            StaffNotification.TYPE_RETRIP_REQUESTED,
            "Re-Trip requested",
            f"{getattr(requested_by, 'employee_name', 'A driver')} asked to end "
            f"{assignment.unique_id} with {pending_total} stop(s) left. Reason: {reason}",
            data={
                "event": "retrip_requested",
                "retrip_request_id": request.unique_id,
                "assignment_id": assignment.unique_id,
                "pending_bin_count": request.pending_bin_count,
                "pending_household_count": request.pending_household_count,
            },
        )

    return request


def _create_continuation_assignment(
    source, *, vehicle_id=None, alt_staff_template_id=None, remarks=None
):
    """A fresh assignment on the SAME trip plan, carrying the leftover work.

    `DailyTripAssignment.save()` clones every plan stop on create (via the
    trip_plan_signals sync), so the caller prunes down to the carried-over
    set afterwards — that is far safer than special-casing the signal.

    `vehicle_id`/`alt_staff_template_id` let a caller swap in a replacement
    vehicle/crew instead of carrying the source's own (used by a vehicle
    breakdown continuation); default to the source's when omitted (the
    plain Re-Trip case).
    """
    continuation = DailyTripAssignment(
        company_id=source.company_id,
        project_id=source.project_id,
        trip_plan_id=source.trip_plan_id,
        staff_template_id=source.staff_template_id,
        alt_staff_template_id=alt_staff_template_id or source.alt_staff_template_id,
        vehicle_id=vehicle_id or source.vehicle_id,
        trip_date=source.trip_date,
        # Continuation starts now, not at the original slot.
        scheduled_time=timezone.localtime().time(),
        status=DailyTripAssignment.STATUS_SCHEDULED,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
        remarks=remarks or f"Re-Trip continuation of {source.unique_id}",
        waste_type_ids=list(source.waste_type_ids or []),
    )
    # Carry the SOURCE trip's waste types/wards, which may be narrower than
    # the plan's.
    continuation.ward_ids = source.ward_ids
    continuation.household_waste_type_ids = source.household_waste_type_ids
    continuation.save()
    return continuation


def _replace_continuation_bins(continuation, pending_bins):
    """Make continuation bin stops mirror the chosen source stops exactly.

    The assignment create signal clones from the current TripPlan. That is a
    useful default for ordinary assignments, but Re-Trip approval must carry
    the source assignment's live pending rows. If the plan changed, its
    catch-all expansion is stale, or the plan cannot expand right now, relying
    on auto-cloned rows can silently create an empty continuation.
    """
    DailyTripCollectionPoint.objects.filter(
        trip_assignment_id=continuation.unique_id
    ).delete()

    rows = []
    for stop in pending_bins:
        rows.append(
            DailyTripCollectionPoint(
                company_id=continuation.company_id,
                project_id=continuation.project_id,
                trip_assignment_id=continuation.unique_id,
                collection_point_id=stop.collection_point_id,
                zone_id=stop.zone_id,
                ward_id=stop.ward_id,
                panchayat_id=stop.panchayat_id,
                bin_id=stop.bin_id,
                sequence=stop.sequence,
                is_collected=False,
                status=DailyTripCollectionPoint.STATUS_PENDING,
                created_by_id=getattr(stop, "created_by_id", None),
            )
        )
    DailyTripCollectionPoint.objects.bulk_create(rows)


def _replace_continuation_households(continuation, pending_households):
    """Make continuation household stops mirror the chosen source stops."""
    DailyTripHouseholdCollection.objects.filter(
        trip_assignment_id=continuation.unique_id
    ).delete()

    rows = []
    for stop in pending_households:
        rows.append(
            DailyTripHouseholdCollection(
                company_id=continuation.company_id,
                project_id=continuation.project_id,
                trip_assignment_id=continuation.unique_id,
                customer_id=stop.customer_id,
                zone_id=stop.zone_id,
                ward_id=stop.ward_id,
                panchayat_id=stop.panchayat_id,
                collection_type=stop.collection_type,
                sequence=stop.sequence,
                is_collected=False,
                status=DailyTripHouseholdCollection.STATUS_PENDING,
                # A customer who said "I'm home now" is still waiting — the
                # continuation crew must see it, and a miss there still
                # raises the Missed Pickup ticket.
                customer_available_at=stop.customer_available_at,
                customer_available_note=stop.customer_available_note,
                created_by_id=getattr(stop, "created_by_id", None),
            )
        )
    DailyTripHouseholdCollection.objects.bulk_create(rows)


def _copy_selected_stops_to_continuation(
    continuation, *, pending_bins, pending_households
):
    _replace_continuation_bins(continuation, pending_bins)
    _replace_continuation_households(continuation, pending_households)

    carried = len(pending_bins) + len(pending_households)
    landed = (
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=continuation.unique_id,
            is_deleted=False,
        ).count()
        + DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=continuation.unique_id,
            is_deleted=False,
        ).count()
    )
    if carried and landed != carried:
        raise ValueError("Continuation trip could not be created with all selected stops.")
    if not landed:
        raise ValueError("Continuation trip would have no collection points.")
    return landed


@transaction.atomic
def create_breakdown_continuation(
    source, *, vehicle_id, alt_staff_template_id, collection_point_ids=None
):
    """Vehicle-breakdown counterpart of `approve_retrip`: open a continuation
    crewed by the replacement vehicle/driver/operator, carrying the same-day
    leftover stops.

    Carry-over rules mirror Re-Trip: live pending source rows are copied
    directly to the continuation. For bin trips, `collection_point_ids`
    restricts which bin stops move; household stops carry when present.
    """
    source = _lock_assignment(source)
    if source is None or source.status in _CLOSED_STATUSES:
        raise ValueError("This trip is already closed.")
    pending_bins = list(source.pending_bin_stops().select_for_update())
    pending_households = list(source.pending_household_stops().select_for_update())
    unselected_bins = []

    if collection_point_ids is not None:
        selected = set(collection_point_ids)
        pending_bin_ids = {stop.unique_id for stop in pending_bins}
        unknown = selected - pending_bin_ids
        if unknown:
            raise ValueError("Selected collection point is not pending on this trip.")
        unselected_bins = [stop for stop in pending_bins if stop.unique_id not in selected]
        pending_bins = [stop for stop in pending_bins if stop.unique_id in selected]

    if not pending_bins and not pending_households:
        raise ValueError("There are no pending stops to carry over.")

    continuation = _create_continuation_assignment(
        source,
        vehicle_id=vehicle_id,
        alt_staff_template_id=alt_staff_template_id,
        remarks=f"Vehicle Breakdown continuation of {source.unique_id}",
    )
    _copy_selected_stops_to_continuation(
        continuation,
        pending_bins=pending_bins,
        pending_households=pending_households,
    )

    DailyTripCollectionPoint.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_bins]
    ).update(carried_to_assignment=continuation.unique_id)
    DailyTripHouseholdCollection.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_households]
    ).update(carried_to_assignment=continuation.unique_id)
    _close_unselected_stops(
        source,
        bins=unselected_bins,
        households=[],
        reason=UNSELECTED_STOP_REASON.format(source=f"breakdown of {source.unique_id}"),
    )
    _supersede_pending_requests(
        source,
        reviewed_by=None,
        continuation=continuation,
        reason="trip closed by vehicle breakdown replacement",
    )

    # The broken vehicle can no longer execute the source assignment. Closing
    # it also releases its existing crew so they may continue on the
    # replacement vehicle without appearing double-booked.
    source.mark_ended()
    source_log = getattr(source, "daily_trip_log", None)
    if source_log is not None:
        source_log.save()

    for staff in _crew_of(source):
        notify_staff(
            staff,
            StaffNotification.TYPE_RETRIP_APPROVED,
            "Vehicle replaced — new trip assigned",
            f"{source.unique_id} has a vehicle breakdown replacement trip "
            f"({continuation.unique_id}) assigned.",
            data={
                "event": "breakdown_continuation",
                "assignment_id": source.unique_id,
                "new_assignment_id": continuation.unique_id,
            },
        )

    return continuation


@transaction.atomic
def approve_retrip(request, *, reviewed_by, collection_point_ids=None, remarks=None):
    """Approve: end the old trip, open a continuation trip.

    `collection_point_ids` are selected pending stop ids. They may refer to
    `DailyTripCollectionPoint.unique_id` or
    `DailyTripHouseholdCollection.unique_id`. Returns the new assignment, or
    None when the request expired first (its window lapsed, or the trip's
    day ended — a continuation dated on a past day would never reach the
    crew's today list).

    Stops the reviewer leaves out are marked Missed on the source, since the
    source is closed here and could never resolve them.
    """
    # Trip first, then request — the same order as request_retrip, so a
    # driver raising a request while a supervisor approves cannot deadlock.
    source = _lock_assignment(request.assignment_id)
    if expire_retrip_if_due(request):
        return None
    request = TripRetripRequest.objects.select_for_update().get(pk=request.pk)
    if not request.is_pending:
        raise RetripRequestUnavailable(
            f"This request was already {request.status.lower()}."
        )
    if timezone.now() >= deadline_for(request):
        expire_retrip_if_due(request)
        return None
    # Closed some other way while this request waited (Proceed Next Trip, a
    # breakdown replacement, the end-of-day closer). Its carried stops still
    # read Pending on the source, so approving now would copy them into a
    # second continuation.
    if source is None or source.status in _CLOSED_STATUSES:
        raise RetripRequestUnavailable("This trip is already closed.")
    from app.models.masters.transport_masters.vehicleCreation import VehicleCreation

    if VehicleCreation.objects.filter(
        unique_id=source.vehicle_id,
        operational_status=VehicleCreation.OperationalStatus.BREAKDOWN,
    ).exists():
        raise ValueError(
            "This trip's vehicle is under breakdown. Use the vehicle breakdown "
            "replacement instead of a re-trip."
        )

    # Resolve what carries over from LIVE data, not the snapshot — a stop may
    # have been collected between the request and this approval. Locked, so
    # a scan landing right now waits for this decision and then sees the stop
    # as carried over, instead of collecting it on the source as well.
    pending_bins = list(source.pending_bin_stops().select_for_update())
    pending_households = list(source.pending_household_stops().select_for_update())
    unselected_bins, unselected_households = [], []

    if collection_point_ids is not None:
        selected = set(collection_point_ids)
        pending_stop_ids = {
            *(stop.unique_id for stop in pending_bins),
            *(stop.unique_id for stop in pending_households),
        }
        unknown = selected - pending_stop_ids
        if unknown:
            raise ValueError("Selected stop is not pending on this trip.")
        unselected_bins = [stop for stop in pending_bins if stop.unique_id not in selected]
        unselected_households = [
            stop for stop in pending_households if stop.unique_id not in selected
        ]
        pending_bins = [stop for stop in pending_bins if stop.unique_id in selected]
        pending_households = [
            stop for stop in pending_households if stop.unique_id in selected
        ]

    continuation = _create_continuation_assignment(source)
    carried = _copy_selected_stops_to_continuation(
        continuation,
        pending_bins=pending_bins,
        pending_households=pending_households,
    )

    # Point the SOURCE stops that carried over at the continuation, so the
    # Daily Trip Plan / Daily Trip Log screens can show "Assigned to Next
    # Trip" instead of a bare Pending with no explanation. Bulk `.update()`
    # — not `.save()` per instance — so it doesn't touch `status`/`updated_at`.
    DailyTripCollectionPoint.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_bins]
    ).update(carried_to_assignment=continuation.unique_id)
    DailyTripHouseholdCollection.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_households]
    ).update(carried_to_assignment=continuation.unique_id)
    _close_unselected_stops(
        source,
        bins=unselected_bins,
        households=unselected_households,
        reason=UNSELECTED_STOP_REASON.format(source=f"Re-Trip {request.unique_id}"),
    )

    # The original trip is done. Its carried-over stops are deliberately left
    # exactly as they are — they stay Pending, since a carried-over stop was genuinely
    # neither collected nor missed today, it moved to the continuation. Do
    # NOT force them to Missed/Not Available: that status feeds the progress
    # count, so bulk-closing them would falsely show the source trip as
    # fully done when nothing more was actually collected.
    source.mark_ended()

    # If a DailyTripLog already exists for the source (created while the trip
    # was still open), refresh it so its actual_start_time/actual_end_time
    # pick up what mark_ended() just stamped on the assignment.
    # autofill_from_assignment() only fills fields that are still empty, so
    # this is safe to call unconditionally.
    source_log = getattr(source, "daily_trip_log", None)
    if source_log is not None:
        source_log.save()

    request.mark_reviewed(
        status=TripRetripRequest.STATUS_APPROVED,
        by=reviewed_by,
        remarks=remarks,
        new_assignment=continuation,
    )

    for staff in _crew_of(source):
        notify_staff(
            staff,
            StaffNotification.TYPE_RETRIP_APPROVED,
            "Re-Trip approved",
            f"{source.unique_id} has been closed. A new trip "
            f"({continuation.unique_id}) with {carried} stop(s) is now on your list.",
            data={
                "event": "retrip_approved",
                "retrip_request_id": request.unique_id,
                "assignment_id": source.unique_id,
                "new_assignment_id": continuation.unique_id,
            },
        )

    return continuation


@transaction.atomic
def proceed_to_next_trip(
    assignment, *, actor, collection_point_ids=None, remarks, reason_code=None
):
    """Web one-step version: a supervisor/admin closes `assignment` and opens
    the continuation directly, instead of a request/approve round trip.

    Reuses `request_retrip`/`approve_retrip` so the audit trail (a Pending
    TripRetripRequest, immediately Approved) and the carry-over rules stay
    in exactly one place. Returns (request, continuation_assignment).

    If the driver already has a Pending request on this trip, that request is
    the one approved (its reason stands; `remarks` become the review
    remarks) — raising a second beside it would leave the driver's Pending,
    and approving it later would duplicate the continuation.
    """
    assignment = _lock_assignment(assignment)
    if assignment is None or assignment.status in _CLOSED_STATUSES:
        raise ValueError("This trip is already closed.")

    request = _live_pending_request(assignment)
    if request is None:
        request = request_retrip(
            assignment, requested_by=actor, reason=remarks, reason_code=reason_code
        )
    continuation = approve_retrip(
        request,
        reviewed_by=actor,
        collection_point_ids=collection_point_ids,
        remarks=remarks,
    )
    if continuation is None:
        raise ValueError(
            "This trip's day has ended, so its stops can no longer move to a new trip."
        )
    return request, continuation


@transaction.atomic
def reject_retrip(request, *, reviewed_by, remarks=None):
    """Decline: the trip stays open and the driver keeps going."""
    if expire_retrip_if_due(request):
        request.refresh_from_db()
        return request
    request = TripRetripRequest.objects.select_for_update().get(pk=request.pk)
    if not request.is_pending:
        raise RetripRequestUnavailable(
            f"This request was already {request.status.lower()}."
        )
    if timezone.now() >= deadline_for(request):
        expire_retrip_if_due(request)
        request.refresh_from_db()
        return request
    request.mark_reviewed(
        status=TripRetripRequest.STATUS_REJECTED,
        by=reviewed_by,
        remarks=remarks,
    )

    for staff in _crew_of(request.assignment):
        notify_staff(
            staff,
            StaffNotification.TYPE_RETRIP_REJECTED,
            "Re-Trip declined",
            f"Your request to end {request.assignment.unique_id} was declined."
            + (f" {remarks}" if remarks else " Please continue the remaining stops."),
            data={
                "event": "retrip_rejected",
                "retrip_request_id": request.unique_id,
                "assignment_id": request.assignment.unique_id,
            },
        )

    return request
