from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.daily_trip_household_collection import DailyTripHouseholdCollection
from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan


def run_for_date(target_date=None, logger=None, force=False):
    """Generate DailyTripAssignment + operational child records for one date.

    This is the single source of truth for the nightly job scheduler. Both
    the `generate_daily_trips` management command (run by the background
    scheduler) and the manual-run API action
    (DailyTripAssignmentViewSet.generate_daily) call this, so the behaviour
    is identical no matter how it is triggered.

    Idempotent: re-running for the same date never creates duplicates because
    every insert is a get_or_create keyed on (trip_plan, trip_date) and
    (trip_assignment, collection_point/bin) or (trip_assignment, customer,
    collection_type).

    Args:
        target_date: a `date` to generate for. Defaults to today (local).
        logger: optional callable(str) for progress lines (e.g. stdout.write).
        force: when True (manual runs), also include not-yet-approved active
            plans and ignore the repeat-day weekday check.

    Returns:
        dict summary: {"date", "weekday", "created", "skipped", "details": [...]}
    """
    today = target_date or timezone.localdate()
    weekday = today.weekday()  # Monday=0 .. Sunday=6

    def log(msg):
        if logger:
            logger(msg)

    plans = TripPlan.objects.filter(
        is_deleted=False,
        status=TripPlan.Status.ACTIVE,
        is_auto_assign=True,
    )
    if not force:
        plans = plans.filter(approval_status=TripPlan.ApprovalStatus.APPROVED)

    created_count = 0
    skipped_count = 0
    details = []

    for plan in plans.select_related("company_id", "project_id").all():
        if not force:
            repeat_days = plan.repeat_days or []
            if not repeat_days:
                # No repeat days configured; nothing to schedule.
                skipped_count += 1
                continue
            try:
                allowed = [int(d) for d in repeat_days]
            except (TypeError, ValueError):
                log(f"TripPlan {plan.unique_id} has invalid repeat_days: {repeat_days}")
                skipped_count += 1
                continue

            if weekday not in allowed:
                # Plan does not run on today's weekday.
                skipped_count += 1
                continue

        defaults = {
            "staff_template_id": plan.staff_template_id,
            "vehicle_id": plan.vehicle_id,
            "panchayat_id": plan.panchayat_id,
            "scheduled_time": plan.scheduled_time,
            "waste_type_ids": plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else []),
        }

        with transaction.atomic():
            assignment, created = DailyTripAssignment.objects.get_or_create(
                company_id=plan.company_id,
                project_id=plan.project_id,
                trip_plan_id=plan,
                trip_date=today,
                defaults=defaults,
            )

            if not created:
                # Duplicate prevention: assignment already exists for this
                # plan+date. Still run the sync as a safety net, in case
                # stops were added to the plan after the assignment existed.
                sync_daily_assignment_stops_from_plan(assignment)
                log(f"Assignment already exists for plan {plan.unique_id} on {today}")
                continue

            if not assignment.wards.exists() and plan.wards.exists():
                assignment.wards.set(plan.wards.all())
            if not assignment.waste_types.exists() and plan.waste_types.exists():
                assignment.waste_types.set(plan.waste_types.all())

            created_count += 1
            # NOTE: a post_save signal on DailyTripAssignment
            # (copy_trip_plan_stops_to_daily_assignment) already clones the
            # stops the moment the assignment is created above. The call
            # below is a safety net for any stop the signal skipped — both
            # paths use get_or_create, so nothing is ever duplicated. We
            # report the TRUE number of child rows that now exist (not just
            # the ones this call inserted), so the summary is accurate
            # regardless of which path won.
            sync_daily_assignment_stops_from_plan(assignment)

            cp_created = DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            ).count()
            hh_created = DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            ).count()

            details.append(
                {
                    "trip_plan_id": plan.unique_id,
                    "assignment_id": assignment.unique_id,
                    "daily_trip_points": cp_created,
                    "household_points": hh_created,
                }
            )
            log(
                f"Created assignment {assignment.unique_id} with {cp_created} "
                f"daily trip points and {hh_created} household points for plan {plan.unique_id}"
            )

    summary = {
        "date": str(today),
        "weekday": weekday,
        "created": created_count,
        "skipped": skipped_count,
        "details": details,
    }
    log(f"Finished. assignments_created={created_count} skipped={skipped_count}")
    return summary


class Command(BaseCommand):
    help = "Generate DailyTripAssignment records from active TripPlan entries (auto-assign)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            help="Optional date (YYYY-MM-DD) to generate trips for. Defaults to today.",
            required=False,
        )
        parser.add_argument(
            "--force",
            dest="force",
            action="store_true",
            help="Include not-yet-approved active plans and ignore repeat-day checks.",
        )

    def handle(self, *args, **options):
        target_date = None
        if options.get("date"):
            try:
                target_date = timezone.datetime.strptime(options["date"], "%Y-%m-%d").date()
            except ValueError as e:
                self.stderr.write(f"Invalid date: {e}")
                return

        run_for_date(
            target_date=target_date,
            logger=self.stdout.write,
            force=bool(options.get("force")),
        )
