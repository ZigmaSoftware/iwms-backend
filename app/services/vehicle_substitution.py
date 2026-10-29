"""Which vehicle (and crew) a trip plan's daily trip runs on, when its own
vehicle is under breakdown.

A `TripPlanVehicleSubstitution` lets a plan keep running on a replacement
vehicle with its own crew until the broken vehicle is repaired. Every place
that creates a daily trip from a plan — the nightly/Run Scheduler job
(`run_for_date`), "Generate selected" (`generate_assignment_for_plan`) and a
manual daily trip — asks `vehicle_for_plan()` instead of reading
`plan.vehicle_id` directly.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_vehicle_substitution import (
    TripPlanVehicleSubstitution,
)
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation

ALL_DAYS = frozenset(range(7))
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

REASON_NO_REPLACEMENT = "Vehicle is under breakdown and no replacement vehicle is set"
REASON_REPLACEMENT_BROKEN = "Vehicle is under breakdown and the replacement vehicle is also under breakdown"

OPEN_TRIP_STATUSES = (
    DailyTripAssignment.STATUS_SCHEDULED,
    DailyTripAssignment.STATUS_IN_PROGRESS,
)


def is_broken_down(vehicle_id):
    return bool(vehicle_id) and VehicleCreation.objects.filter(
        unique_id=vehicle_id,
        operational_status=VehicleCreation.OperationalStatus.BREAKDOWN,
    ).exists()


def plan_days(plan):
    """Weekdays (Mon=0) a plan runs on. No repeat days = every day, the
    same reading as daily_trip_generation.should_generate_for_date."""
    try:
        days = {int(day) for day in (plan.repeat_days or [])}
    except (TypeError, ValueError):
        return set()
    return days or set(ALL_DAYS)


def day_names(days):
    return [DAY_NAMES[day] for day in sorted(days) if 0 <= day < 7]


# ── Lookups ───────────────────────────────────────────────────────────


def active_substitutions():
    return TripPlanVehicleSubstitution.objects.filter(
        status=TripPlanVehicleSubstitution.STATUS_ACTIVE,
        is_deleted=False,
    )


def substitution_for(plan, on_date):
    """The substitution covering `plan` on `on_date`. One made for an older
    vehicle of the plan (its vehicle was changed since) does not count."""
    return (
        active_substitutions()
        .filter(
            trip_plan_id=plan.unique_id,
            original_vehicle_id=plan.vehicle_id,
            from_date__lte=on_date,
        )
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=on_date))
        .order_by("-created_at")
        .first()
    )


def vehicle_for_plan(plan, on_date):
    """(vehicle_id, None) for the vehicle the plan's trip runs on that day,
    or (None, reason) when it cannot run: its vehicle is under breakdown with
    no usable replacement."""
    if not is_broken_down(plan.vehicle_id):
        return plan.vehicle_id, None
    substitution = substitution_for(plan, on_date)
    if substitution is None:
        return None, REASON_NO_REPLACEMENT
    if is_broken_down(substitution.replacement_vehicle_id):
        return None, REASON_REPLACEMENT_BROKEN
    return substitution.replacement_vehicle_id, None


def alternative_crew_for(staff_template_id, on_date):
    """An approved, dated alternative crew covering `on_date` for this staff
    template. Breakdown replacement crews are undated, so never match."""
    if not staff_template_id:
        return None
    return (
        AlternativeStaffTemplate.objects.filter(
            staff_template_id=staff_template_id,
            approval_status="APPROVED",
            is_deleted=False,
            from_date__isnull=False,
            from_date__lte=on_date,
        )
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=on_date))
        .order_by("-created_at")
        .first()
    )


# ── Clash checks (warn, supervisor confirms) ──────────────────────────


def plan_clashes(replacement_vehicle_id, plan, from_date):
    """Regular work the replacement vehicle already has on the plan's days:
    its own active trip plans, and plans it already stands in for."""
    days = plan_days(plan)
    clashes = []
    own_plans = TripPlan.objects.filter(
        vehicle_id=replacement_vehicle_id,
        status=TripPlan.Status.ACTIVE,
        is_deleted=False,
    ).exclude(unique_id=plan.unique_id)
    for other in own_plans:
        common = days & plan_days(other)
        if common:
            clashes.append({
                "kind": "own_plan",
                "trip_plan_id": other.unique_id,
                "display_code": other.display_code,
                "scheduled_time": str(other.scheduled_time) if other.scheduled_time else None,
                "days": day_names(common),
            })
    standing_in = (
        active_substitutions()
        .filter(replacement_vehicle_id=replacement_vehicle_id)
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=from_date))
        .exclude(trip_plan_id=plan.unique_id)
    )
    other_plans = {
        p.unique_id: p
        for p in TripPlan.objects.filter(
            unique_id__in=standing_in.values("trip_plan_id"), is_deleted=False,
        )
    }
    for substitution in standing_in:
        other = other_plans.get(substitution.trip_plan_id)
        common = days & plan_days(other) if other else set()
        if common:
            clashes.append({
                "kind": "substitution",
                "trip_plan_id": other.unique_id,
                "display_code": other.display_code,
                "scheduled_time": str(other.scheduled_time) if other.scheduled_time else None,
                "days": day_names(common),
            })
    return clashes


def busy_trips_on(vehicle_id, trip_date, exclude_ids=()):
    """The vehicle's other unfinished trips that day."""
    return list(
        DailyTripAssignment.objects.filter(
            vehicle_id=vehicle_id,
            trip_date=trip_date,
            status__in=OPEN_TRIP_STATUSES,
            is_deleted=False,
        )
        .exclude(unique_id__in=list(exclude_ids))
        .order_by("scheduled_time")
        .values("unique_id", "scheduled_time")
    )


# ── Create / end ──────────────────────────────────────────────────────


def create_substitution(plan, replacement_vehicle_id, from_date, *, breakdown_id=None, created_by_id=None):
    """Start running `plan` on `replacement_vehicle_id` from `from_date`.
    Ends any substitution the plan already has — a plan uses one at a time."""
    end_substitutions(
        active_substitutions().filter(trip_plan_id=plan.unique_id),
        "Replaced by a new substitution",
    )
    return TripPlanVehicleSubstitution.objects.create(
        company_id=plan.company_id,
        project_id=plan.project_id,
        trip_plan_id=plan.unique_id,
        original_vehicle_id=plan.vehicle_id,
        replacement_vehicle_id=replacement_vehicle_id,
        vehicle_breakdown_id=breakdown_id,
        from_date=from_date,
        created_by_id=created_by_id,
    )


def end_substitutions(queryset, reason):
    now = timezone.now()
    return queryset.update(
        status=TripPlanVehicleSubstitution.STATUS_ENDED,
        ended_at=now,
        end_reason=reason[:200],
        updated_at=now,
    )


def end_for_repaired_vehicle(vehicle_id):
    """The broken vehicle is back in service: its plans go back to it."""
    return end_substitutions(
        active_substitutions().filter(original_vehicle_id=vehicle_id),
        "Vehicle back in service",
    )


def end_for_plan_vehicle_change(plan):
    return end_substitutions(
        active_substitutions().filter(trip_plan_id=plan.unique_id).exclude(
            original_vehicle_id=plan.vehicle_id,
        ),
        "Trip plan vehicle changed",
    )


# ── Verify preview ────────────────────────────────────────────────────


def plans_of_vehicle(vehicle_id):
    return TripPlan.objects.filter(
        vehicle_id=vehicle_id,
        status=TripPlan.Status.ACTIVE,
        is_deleted=False,
    ).order_by("scheduled_time", "display_code")


def substitution_start(breakdown):
    """Substitutions cover the days after the breakdown's trip; that day
    itself is handled by the continuation and the moved trips."""
    source = breakdown.trip_assignment
    day = source.trip_date if source else timezone.localdate()
    return day + timedelta(days=1)


def verify_preview(breakdown, replacement_vehicle_id):
    """What Verify & Approve will offer for `replacement_vehicle_id`:

    - upcoming_trips: the broken vehicle's not-started trips, each with the
      replacement's other trips that day. Ticked by default only when the
      replacement has nothing else that day.
    - plans: the broken vehicle's trip plans for the days after, each with
      the replacement's clashing regular work. Ticked by default only when
      there is no clash.
    """
    from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
        upcoming_trips_of_broken_vehicle,
    )

    exclude = [breakdown.trip_assignment_id] if breakdown.trip_assignment_id else []
    trips = []
    for trip in upcoming_trips_of_broken_vehicle(breakdown):
        busy = (
            busy_trips_on(replacement_vehicle_id, trip.trip_date, exclude_ids=exclude)
            if replacement_vehicle_id
            else []
        )
        trips.append({
            "unique_id": trip.unique_id,
            "trip_date": str(trip.trip_date),
            "scheduled_time": str(trip.scheduled_time) if trip.scheduled_time else None,
            "trip_plan_display_code": getattr(trip.trip_plan, "display_code", None),
            "replacement_busy": [
                {
                    "unique_id": row["unique_id"],
                    "scheduled_time": str(row["scheduled_time"]) if row["scheduled_time"] else None,
                }
                for row in busy
            ],
            "default_move": bool(replacement_vehicle_id) and not busy,
        })

    from_date = substitution_start(breakdown)
    plans = []
    for plan in plans_of_vehicle(breakdown.breakdown_vehicle_id):
        clashes = plan_clashes(replacement_vehicle_id, plan, from_date) if replacement_vehicle_id else []
        plans.append({
            "trip_plan_id": plan.unique_id,
            "display_code": plan.display_code,
            "scheduled_time": str(plan.scheduled_time) if plan.scheduled_time else None,
            "days": day_names(plan_days(plan)),
            "clashes": clashes,
            "default_substitute": bool(replacement_vehicle_id) and not clashes,
        })

    return {
        "replacement_vehicle_id": replacement_vehicle_id,
        "substitute_from_date": str(from_date),
        "upcoming_trips": trips,
        "plans": plans,
    }


# ── Supervisor alert (S6/S8) ──────────────────────────────────────────


def alert_plan_not_scheduled(plan, on_date, reason):
    """Tell the plan's supervisor its trip was not created — once per plan
    per day, however many times the scheduler runs."""
    from app.models.core_modules.notifications.staff_notification import StaffNotification
    from app.services.staff_notification_service import notify_staff

    supervisor = plan.supervisor
    if supervisor is None:
        return None
    already_sent = StaffNotification.objects.filter(
        recipient_staff_id=supervisor.staff_unique_id,
        notification_type=StaffNotification.TYPE_TRIP_NOT_SCHEDULED,
        data__trip_plan_id=plan.unique_id,
        data__date=str(on_date),
    ).exists()
    if already_sent:
        return None
    return notify_staff(
        supervisor,
        StaffNotification.TYPE_TRIP_NOT_SCHEDULED,
        title="Trip not created",
        body=(
            f"{plan.display_code or plan.unique_id} was not scheduled for {on_date}: "
            f"{reason}. Set a replacement vehicle on the trip plan, then generate it."
        ),
        data={"trip_plan_id": plan.unique_id, "date": str(on_date), "reason": reason},
    )
