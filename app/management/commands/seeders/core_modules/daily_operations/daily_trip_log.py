from datetime import datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.base_models import Account


class DailyTripLogSeeder(BaseSeeder):
    name = "daily_trip_log"
    target = 90

    def run(self):
        assignments = (
            DailyTripAssignment.objects.select_related(
                "company_id",
                "project_id",
                "trip_plan_id",
                "trip_plan_id__vehicle_id",
                "staff_template_id",
                "staff_template_id__driver_id",
                "staff_template_id__operator_id",
                "alt_staff_template_id",
                "alt_staff_template_id__driver_id",
                "alt_staff_template_id__operator_id",
                "panchayat_id",
            )
            .filter(is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .order_by("-trip_date", "-scheduled_time")
        )

        if not assignments:
            self.log("DailyTripLogSeeder skipped (no daily trip assignments).")
            return

        # Waste comparison reports show every trip log regardless of status,
        # so mix Unverified/Verified rows to demonstrate both states.
        statuses = [
            DailyTripLog.LOG_STATUS_UNVERIFIED,
            DailyTripLog.LOG_STATUS_VERIFIED,
        ]
        verifier = Account.objects.first()
        created = 0
        skipped = 0
        eligible_processed = 0

        for idx, assignment in enumerate(assignments):
            if not assignment.panchayat_id:
                skipped += 1
                continue
            if eligible_processed >= self.target:
                break
            eligible_processed += 1
            existing_log = DailyTripLog.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            ).first()
            if existing_log:
                skipped += 1
                continue

            trip_plan = assignment.trip_plan_id
            vehicle = assignment.vehicle_id or getattr(trip_plan, "vehicle_id", None)
            staff_template = assignment.alt_staff_template_id or assignment.staff_template_id
            if not vehicle or not staff_template:
                skipped += 1
                continue

            capacity = vehicle.capacity or trip_plan.max_vehicle_capacity_kg or 1000
            capacity_decimal = Decimal(str(capacity))
            factor = Decimal("0.55") + (Decimal(idx) * Decimal("0.05"))
            collected_weight = min(
                capacity_decimal * factor,
                capacity_decimal - Decimal("1"),
            ).quantize(Decimal("0.01"))
            log_status = statuses[idx % len(statuses)]

            # Stamp REAL timestamps on the assignment itself (idempotent —
            # a no-op if it already started/ended) rather than fabricating
            # start/end times directly on the log: that used to leave a log
            # with times that had nothing to do with the assignment's own
            # actual_start_at/actual_end_at, which broke the Verify gate
            # (Verify requires the trip to have actually ended).
            start_at = timezone.make_aware(
                datetime.combine(assignment.trip_date, time(7 + (idx % 3), 30))
            )
            end_at = timezone.make_aware(
                datetime.combine(assignment.trip_date, time(10 + (idx % 4), 15))
            )
            assignment.mark_started(at=start_at)
            assignment.mark_ended(at=end_at)

            log = DailyTripLog.objects.create(
                trip_assignment_id=assignment,
                # actual_start_time/actual_end_time deliberately omitted —
                # autofill_from_assignment() (called from save()) mirrors
                # them from the assignment above, so log and assignment can
                # never disagree.
                collected_weight_kg=collected_weight,
                remarks=f"Seeder demo {log_status.lower()} trip log for {assignment.unique_id}",
                log_status=log_status,
                verified_by=verifier if log_status == DailyTripLog.LOG_STATUS_VERIFIED else None,
                verified_at=(
                    timezone.now() - timedelta(hours=idx)
                    if log_status == DailyTripLog.LOG_STATUS_VERIFIED
                    else None
                ),
            )

            bin_qs = Bins.objects.filter(
                company_id=assignment.company_id,
                project_id=assignment.project_id,
                is_deleted=False,
            ).order_by("bin_name")[:3]
            if bin_qs:
                log.bin_ids.set(bin_qs)

            extra_ids = (
                getattr(staff_template, "extra_operator_id", None)
                or getattr(staff_template, "extra_operator_ids", None)
                or []
            )
            extra_staff = Staffcreation.objects.filter(staff_unique_id__in=extra_ids)
            if extra_staff:
                log.extra_operator_ids.set(extra_staff)

            created += 1

        self.log(f"---Daily trip logs seeded | Created: {created} | Skipped: {skipped}---")
