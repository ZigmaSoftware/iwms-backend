"""Backfill panchayat_id on DailyTripLog rows that are NULL.

Ward-based (household) trips were saved before the autofill logic was
updated to derive panchayat from the first ward.  Run once to fix historical
records so they appear in the Daily/Monthly Waste Comparison reports.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from app.models.schedule_masters.daily_trip_log import DailyTripLog


class Command(BaseCommand):
    help = "Backfill panchayat_id on DailyTripLog rows where it is NULL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be updated without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        logs = (
            DailyTripLog.objects.filter(
                is_deleted=False,
                panchayat_id__isnull=True,
            )
            .select_related("trip_assignment_id")
            .prefetch_related("trip_assignment_id__wards__panchayat_id")
        )

        updated = 0
        skipped = 0

        for log in logs:
            assignment = log.trip_assignment_id
            if not assignment:
                skipped += 1
                continue

            first_ward = assignment.wards.select_related("panchayat_id").first()
            if not first_ward or not first_ward.panchayat_id_id:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"Would update {log.unique_id}: panchayat_id = {first_ward.panchayat_id_id}"
                )
            else:
                with transaction.atomic():
                    DailyTripLog.objects.filter(pk=log.pk).update(
                        panchayat_id=first_ward.panchayat_id_id,
                    )
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{'[DRY RUN] Would update' if dry_run else 'Updated'} {updated} logs, skipped {skipped}."
            )
        )
