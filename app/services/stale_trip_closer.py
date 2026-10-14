"""End-of-day closer for trips that were started but never finished.

Nothing else closes a trip: a driver must resolve every stop or request a
Re-Trip, so a trip abandoned mid-way stays `In Progress` forever and the
supervisor sees it under "From earlier days" indefinitely.

For every assignment dated BEFORE `today` that is still `In Progress`:

  * every unresolved stop (bin and household) is marked Missed / Not
    Available with an explanatory reason,
  * a remark says the system closed the trip,
  * the trip is closed as `Completed` (stamped at the end of its own date, so
    the duration never spans into the next day), and its DailyTripLog is
    refreshed so it appears in History.

Trips waiting on a supervisor decision (a pending Re-Trip request or a pending
vehicle-breakdown review) are skipped: that decision is the supervisor's, and
closing underneath it would discard it. They are picked up on a later run once
decided. `Scheduled` trips are left alone — they never started, so "Completed"
would be false.
"""

import logging
from datetime import datetime, time

from django.db import transaction
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.trip_retrip_request import (
    TripRetripRequest,
)
from app.models.core_modules.daily_operations.vehicle_breakdown import (
    VehicleBreakdown,
)

logger = logging.getLogger(__name__)

STOP_REASON = "Not collected: trip closed automatically at end of day."
TRIP_REMARK = (
    "Closed automatically by the system at end of day. "
    "{count} unresolved stop(s) were marked as missed."
)


def _has_pending_decision(assignment):
    if TripRetripRequest.objects.filter(
        assignment_id=assignment.unique_id,
        status=TripRetripRequest.STATUS_PENDING,
        is_deleted=False,
    ).exists():
        return True
    return VehicleBreakdown.objects.filter(
        trip_assignment_id=assignment.unique_id,
        approval_status=VehicleBreakdown.APPROVAL_PENDING,
        is_deleted=False,
    ).exists()


def _end_of_trip_day(trip_date):
    return timezone.make_aware(datetime.combine(trip_date, time(23, 59, 59)))


@transaction.atomic
def _close_one(assignment):
    pending_bins = assignment.pending_bin_stops()
    pending_households = assignment.pending_household_stops()
    count = pending_bins.count() + pending_households.count()

    # QuerySet.update(): these are system closures, not driver actions, so the
    # per-stop mark_status() side effects (assignment auto-end checks) are
    # unwanted — the trip is closed explicitly below.
    pending_bins.update(
        status=DailyTripCollectionPoint.STATUS_MISSED,
        status_reason=STOP_REASON,
        is_collected=False,
        collected_weight_kg=None,
        updated_at=timezone.now(),
    )
    pending_households.update(
        status=DailyTripHouseholdCollection.STATUS_MISSED,
        status_reason=STOP_REASON,
        is_collected=False,
        collected_weight_kg=None,
        updated_at=timezone.now(),
    )

    remark = TRIP_REMARK.format(count=count)
    assignment.remarks = (
        f"{assignment.remarks}\n{remark}" if assignment.remarks else remark
    )
    assignment.save(update_fields=["remarks", "updated_at"])

    ended_at = max(
        _end_of_trip_day(assignment.trip_date),
        assignment.actual_start_at or _end_of_trip_day(assignment.trip_date),
    )
    assignment.mark_ended(at=ended_at)

    # Refresh the log (if one exists) so it picks up the end time just stamped;
    # autofill only fills still-empty fields, so this is safe.
    log = getattr(assignment, "daily_trip_log", None)
    if log is not None:
        log.save()
    return count


def close_stale_trips(today=None, log=None):
    """Close every past-dated In Progress trip. Returns a summary dict."""
    today = today or timezone.localdate()
    log = log or logger
    stale = DailyTripAssignment.objects.filter(
        trip_date__lt=today,
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        is_deleted=False,
    ).order_by("trip_date", "unique_id")

    closed, skipped, failed, stops_missed = [], [], [], 0
    for assignment in stale:
        try:
            if _has_pending_decision(assignment):
                skipped.append(assignment.unique_id)
                continue
            stops_missed += _close_one(assignment)
            closed.append(assignment.unique_id)
        except Exception:
            # One bad trip must not stop the rest from being closed.
            log.exception("Could not auto-close trip %s", assignment.unique_id)
            failed.append(assignment.unique_id)

    result = {
        "closed": closed,
        "skipped_pending_decision": skipped,
        "failed": failed,
        "stops_marked_missed": stops_missed,
    }
    log.info(
        "Stale trip closer: %d closed, %d skipped, %d failed",
        len(closed), len(skipped), len(failed),
    )
    return result
