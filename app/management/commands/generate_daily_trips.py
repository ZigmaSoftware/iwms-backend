from django.core.management.base import BaseCommand
from django.utils import timezone

from app.services.daily_trip_generation import (
    active_auto_assign_plans,
    generate_assignment_for_plan,
    should_generate_for_date,
)


class Command(BaseCommand):
    help = "Generate DailyTripAssignment records from active TripPlan entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            help="Optional date (YYYY-MM-DD) to generate trips for. Defaults to today.",
            required=False,
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Generate from all active trip plans for the date, ignoring approval and repeat-day filters.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        if options.get("date"):
            try:
                today = timezone.datetime.strptime(options.get("date"), "%Y-%m-%d").date()
            except Exception as e:
                self.stderr.write(f"Invalid date: {e}")
                return

        force = bool(options.get("force"))
        plans = active_auto_assign_plans(force=force)

        created_count = 0
        existing_count = 0
        cp_created_count = 0
        skipped_count = 0
        error_count = 0
        for plan in plans.all():
            if not should_generate_for_date(plan, today, force=force):
                skipped_count += 1
                continue

            try:
                assignment, created, cp_created = generate_assignment_for_plan(plan, today)
            except Exception as exc:
                error_count += 1
                self.stderr.write(f"TripPlan {plan.unique_id} failed: {exc}")
                continue

            cp_created_count += cp_created
            if created:
                created_count += 1
                self.stdout.write(
                    f"Created assignment {assignment.unique_id} with {cp_created} collection points for plan {plan.unique_id}"
                )
            else:
                existing_count += 1
                self.stdout.write(
                    f"Assignment already exists for plan {plan.unique_id} on {today}; added {cp_created} missing collection points"
                )

        self.stdout.write(
            "Finished. "
            f"assignments_created={created_count} "
            f"assignments_existing={existing_count} "
            f"collection_points_created={cp_created_count} "
            f"skipped={skipped_count} "
            f"errors={error_count}"
        )
