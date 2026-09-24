from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog


class Command(BaseCommand):
    help = "Create missing DailyTripLog rows for daily trip assignments that have collection points."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            dest="company_id",
            required=False,
            help="Optional company unique_id filter.",
        )
        parser.add_argument(
            "--project-id",
            dest="project_id",
            required=False,
            help="Optional project unique_id filter.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        logged_assignment_ids = DailyTripLog.objects.exclude(
            trip_assignment_id__isnull=True,
        ).values("trip_assignment_id")
        assignments = DailyTripAssignment.objects.filter(
            is_deleted=False,
        ).exclude(
            status=DailyTripAssignment.STATUS_CANCELLED,
        ).exclude(
            unique_id__in=logged_assignment_ids,
        )

        if options.get("company_id"):
            assignments = assignments.filter(company_id=options["company_id"])
        if options.get("project_id"):
            assignments = assignments.filter(project_id=options["project_id"])

        created = 0
        submitted = 0
        skipped = 0
        for assignment in assignments:
            children = assignment.trip_collection_points.filter(is_deleted=False)
            if not children.exists():
                skipped += 1
                continue

            all_collected = not children.filter(is_collected=False).exists()
            if all_collected and assignment.status != DailyTripAssignment.STATUS_COMPLETED:
                assignment.mark_completed_if_all_cps_collected()

            total_weight = children.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
            vehicle_capacity = getattr(assignment.vehicle, "capacity", None)
            trip_capacity = getattr(assignment.trip_plan, "max_vehicle_capacity_kg", None)
            capacity = vehicle_capacity or trip_capacity
            exceeds_capacity = (
                bool(capacity)
                and total_weight
                and Decimal(str(total_weight)) > Decimal(str(capacity))
            )
            stored_weight = None if exceeds_capacity else total_weight
            remarks = (
                "Backfilled from daily trip collection points; total weight exceeds capacity."
                if exceeds_capacity
                else "Backfilled from daily trip collection points."
            )

            DailyTripLog.objects.create(
                trip_assignment_id=assignment.unique_id,
                collected_weight_kg=stored_weight,
                remarks=remarks,
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Daily trip log backfill complete. "
                f"created={created} skipped={skipped}"
            )
        )
