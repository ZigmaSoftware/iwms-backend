from django.db import transaction

from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint

# NOTE: the authoritative nightly/manual auto-assign entry point is
# `run_for_date()` in app/management/commands/generate_daily_trips.py — it
# owns the is_auto_assign / approval / repeat-day filtering and delegates
# stop-cloning to app.signals.trip_plan_signals.sync_daily_assignment_stops_from_plan
# (the single source of truth for bin + household + bulk cloning, shared
# with the post_save signal on DailyTripAssignment). The helpers below are
# kept for two unrelated, still-active call sites:
#   - `ensure_assignment_collection_points`: manual bin-stop resync used by
#     DailyTripAssignmentSerializer._sync_collection_points when an admin
#     edits a daily assignment's collection points directly.
#   - `generate_daily_trips_for_date`: legacy seeder-facing wrapper, now a
#     thin adapter over `run_for_date` so seeders get the same behaviour.


def should_generate_for_date(plan: TripPlan, target_date, force: bool = False) -> bool:
    if force:
        return True
    repeat_days = plan.repeat_days or []
    if not repeat_days:
        return True
    try:
        allowed_days = {int(day) for day in repeat_days}
    except (TypeError, ValueError):
        return False
    return target_date.weekday() in allowed_days


def active_auto_assign_plans(force: bool = False):
    """Active plans flagged for auto-assign. Requires `is_auto_assign=True` —
    without this filter EVERY active plan would be picked up regardless of
    the flag, which was a bug (see app/management/commands/generate_daily_trips.py
    run_for_date for the authoritative, identical filter)."""
    queryset = TripPlan.objects.filter(
        is_deleted=False,
        status=TripPlan.Status.ACTIVE,
        is_auto_assign=True,
    )
    if not force:
        queryset = queryset.filter(
            approval_status=TripPlan.ApprovalStatus.APPROVED,
        )
    return queryset.select_related("company_id", "project_id")


def ensure_assignment_collection_points(assignment: DailyTripAssignment, created_by=None) -> int:
    if not assignment or not assignment.trip_plan_id_id:
        return 0

    existing_stop_keys = set(
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment,
            is_deleted=False,
        ).values_list("collection_point_id_id", "bin_id_id")
    )
    stops = (
        TripPlanCollectionPoint.objects.filter(
            trip_plan_id=assignment.trip_plan_id,
            # Collection points support bin + bulk only. Bulk stops with a
            # linked bin are auto-assigned alongside bin stops; stops without
            # a bin are excluded below (DailyTripCollectionPoint needs a bin).
            collection_type__in=[
                TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                Collection_point.COLLECTION_TYPE_BULK,
            ],
            is_active=True,
            is_deleted=False,
        )
        .exclude(collection_point_id__isnull=True)
        .exclude(bin_id__isnull=True)
        .select_related("collection_point_id", "bin_id")
        .order_by("sequence")
    )

    created_count = 0
    for stop in stops:
        stop_key = (stop.collection_point_id_id, stop.bin_id_id)
        if stop_key in existing_stop_keys:
            continue
        DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment,
            collection_point_id=stop.collection_point_id,
            bin_id=stop.bin_id,
            sequence=stop.sequence,
            is_collected=False,
            status=DailyTripCollectionPoint.STATUS_PENDING,
            created_by=created_by,
        )
        existing_stop_keys.add(stop_key)
        created_count += 1
    return created_count


@transaction.atomic
def generate_assignment_for_plan(plan: TripPlan, target_date, created_by=None):
    """Create (or fetch) the DailyTripAssignment for one plan + date and
    clone its stops via the single authoritative cloning path
    (sync_daily_assignment_stops_from_plan), then top up any bin/bulk stops
    via ensure_assignment_collection_points (idempotent, so this never
    duplicates rows the signal already created).

    Not a plain get_or_create(): a Re-Trip continuation (see
    app/services/retrip_service.py) is deliberately a second assignment on
    the same (trip_plan_id, trip_date) as the source it closes out, so more
    than one row can legitimately exist for that pair — get_or_create()'s
    implicit .get() would raise MultipleObjectsReturned once that happens.
    Treat the oldest row as "the" assignment for this plan/date instead."""
    from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan

    defaults = {
        "staff_template_id": plan.staff_template_id,
        "vehicle_id": plan.vehicle_id,
        "waste_type_ids": plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else []),
        "panchayat_id": plan.panchayat_id,
        "scheduled_time": plan.scheduled_time,
    }
    assignment = (
        DailyTripAssignment.objects.filter(
            company_id=plan.company_id,
            project_id=plan.project_id,
            trip_plan_id=plan,
            trip_date=target_date,
        )
        .order_by("created_at")
        .first()
    )
    created = assignment is None
    if created:
        assignment = DailyTripAssignment.objects.create(
            company_id=plan.company_id,
            project_id=plan.project_id,
            trip_plan_id=plan,
            trip_date=target_date,
            **defaults,
        )
    if not created:
        update_fields = []
        if not assignment.waste_type_ids:
            assignment.waste_type_ids = plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else [])
            update_fields.append("waste_type_ids")
        if update_fields:
            assignment.save(update_fields=update_fields)
    if not assignment.wards.exists() and plan.wards.exists():
        assignment.wards.set(plan.wards.all())
    if not assignment.waste_types.exists() and plan.waste_types.exists():
        assignment.waste_types.set(plan.waste_types.all())

    # Safety net: covers stops added to the plan after the assignment
    # existed, and household/bulk stops that ensure_assignment_collection_points
    # (bin/bulk-with-bin only) doesn't handle.
    sync_daily_assignment_stops_from_plan(assignment)

    cp_created = ensure_assignment_collection_points(
        assignment,
        created_by=created_by,
    )
    return assignment, created, cp_created


def generate_daily_trips_for_date(target_date, force: bool = False):
    """Legacy seeder-facing wrapper. Delegates to `run_for_date` (the
    authoritative auto-assign entry point shared with the management command,
    scheduler, and manual API action) and reshapes the summary into the
    older field names some seeders still expect."""
    from app.management.commands.generate_daily_trips import run_for_date

    summary = run_for_date(target_date=target_date, force=force)
    point_count = sum(
        (d.get("daily_trip_points", 0) + d.get("household_points", 0))
        for d in summary.get("details", [])
    )
    return {
        "assignments_created": summary["created"],
        "assignments_existing": 0,
        "collection_points_created": point_count,
        "skipped": summary["skipped"],
        "errors": [],
    }
