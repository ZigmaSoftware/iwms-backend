"""
Management command: promote_draft_trip_logs

Finds all Draft DailyTripLog records where every collection point on the
linked trip assignment is already collected, then promotes them to Submitted
and backfills collected_weight_kg from the assignment's collection points.

Usage:
    python manage.py promote_draft_trip_logs
    python manage.py promote_draft_trip_logs --dry-run
    python manage.py promote_draft_trip_logs --company CMP-xxx
    python manage.py promote_draft_trip_logs --project PROJ-xxx
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint


class Command(BaseCommand):
    help = "Promote completed Draft trip logs to Submitted so they appear in waste comparison reports."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report without saving.")
        parser.add_argument("--company", help="Filter by company unique_id.")
        parser.add_argument("--project", help="Filter by project unique_id.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        company = options.get("company")
        project = options.get("project")

        qs = DailyTripLog.objects.select_related(
            "trip_assignment_id", "trip_assignment_id__vehicle_id",
            "trip_assignment_id__trip_plan_id",
        ).filter(
            is_deleted=False,
            log_status=DailyTripLog.LOG_STATUS_DRAFT,
        )
        if company:
            qs = qs.filter(company_id__unique_id=company)
        if project:
            qs = qs.filter(project_id__unique_id=project)

        promoted = 0
        skipped = 0

        for log in qs.iterator():
            assignment = log.trip_assignment_id
            if not assignment:
                skipped += 1
                continue

            children = DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment,
                is_deleted=False,
            )
            if not children.exists():
                skipped += 1
                continue

            all_collected = not children.filter(is_collected=False).exists()
            if not all_collected:
                skipped += 1
                continue

            total_weight = children.aggregate(total=Sum("collected_weight_kg"))["total"] or Decimal("0")
            if not total_weight:
                skipped += 1
                continue

            self.stdout.write(
                f"  {'[DRY RUN] ' if dry_run else ''}Promoting {log.unique_id} "
                f"(assignment {assignment.unique_id}, weight {total_weight} kg)"
            )

            if not dry_run:
                log.collected_weight_kg = total_weight
                log.log_status = DailyTripLog.LOG_STATUS_SUBMITTED
                log.save(update_fields=["collected_weight_kg", "log_status", "updated_at"])

            promoted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Done — "
                f"{promoted} promoted, {skipped} skipped."
            )
        )
