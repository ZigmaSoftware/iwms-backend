from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.wastecollection import WasteCollection
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.services import retrip_service
from app.services.daily_trip_generation import generate_assignment_for_plan

# This demo's assignments are deliberately built on today's date: any seeder
# that sweeps trip history and fully resolves its stops skips today, so
# keeping to today is what protects the deliberately partial state created
# here from being flattened. driver_user/operator_user is the mobile-app demo
# login (see StaffTemplateSeeder) — its trip plan is excluded so this demo
# never collides with a hand-driven mobile session.
DEMO_STAFF_USERNAMES = {"driver_user", "operator_user"}
DEMO_STAFF_TEMPLATE_UNIQUE_IDS = set()

REMARKS = "Truck full — proceeding to weighment. Seeded Re-Trip demo scenario."

# (wet, dry, mixed, sanitary) kg presets — cycled through for varied,
# reproducible data. Previously imported from the deleted WasteCollectionSeeder
# module; inlined here, its only remaining consumer.
WASTE_PRESETS = [
    (3.5, 1.2, 0.0, 0.0),
    (2.0, 2.5, 0.5, 0.2),
    (5.0, 0.0, 1.0, 0.0),
    (1.5, 1.5, 0.0, 0.3),
    (4.2, 3.1, 0.8, 0.0),
    (0.0, 2.0, 3.0, 0.4),
    (6.0, 1.0, 0.0, 0.1),
    (2.8, 2.8, 1.4, 0.2),
]


def _split_for_partial_completion(total):
    """How many stops to mark collected vs. leave pending. Mirrors the exact
    shape from the product ask when there's enough to split — 5 stops, 3
    collected, 2 left for the next trip. Most seeded trip plans in a smaller
    demo dataset only carry a single stop; rather than skip those entirely,
    a 1-stop trip is left fully pending, which is still a genuine (if less
    illustrative) 'one outstanding stop, carry it over' scenario."""
    if total <= 0:
        return None
    if total == 1:
        return 0, 1
    pending = min(total - 1, max(2, total // 3))
    return total - pending, pending


class RetripDemoSeeder(BaseSeeder):
    """Seeds the Re-Trip / 'Proceed with Next Trip' scenarios end-to-end —
    the Re-Trip Requests screen has nothing to show against without this,
    since nothing else creates a TripRetripRequest.

    Reserves 3 distinct, already-seeded TripPlans (2 bin + 1 household) for
    one dedicated "today" assignment each, so it never collides with the
    generic week-of-history walk:

      1. Bin trip       — partial completion, `proceed_to_next_trip()` (web
                          one-step): continuation created, selected pending
                          CPs get `carried_to_assignment` set, source ends.
      2. Household trip — partial completion, `proceed_to_next_trip()` with
                          no CP selection: every remaining household
                          auto-carries (the product rule for households).
      3. Bin trip       — partial completion, `request_retrip()` only: stays
                          In Progress with a Pending TripRetripRequest — the
                          scenario for testing the Re-Trip Requests approval
                          queue on an untouched, still-open trip.
      4. Bin trip       — partial completion, `request_retrip()` then
                          `reject_retrip()`: stays In Progress with a
                          Rejected TripRetripRequest, for queue history/filter
                          coverage.

    Idempotent: re-running finds the same (trip_plan, today) assignments via
    get_or_create and skips any stage whose result already exists (a
    TripRetripRequest for that assignment, or a source already Completed).
    """

    name = "retrip_demo"

    # ------------------------------------------------------------------
    def run(self):
        today = timezone.localdate()

        bin_plans = self._eligible_plans(TripPlan.COLLECTION_TYPE_BIN, limit=3)
        household_plans = self._eligible_plans(TripPlan.COLLECTION_TYPE_HOUSEHOLD, limit=1)

        if len(bin_plans) < 3:
            self.log_error(
                f"Need 3 distinct bin-collection TripPlans with complete staff/vehicle, "
                f"found {len(bin_plans)} — seed schedule-setup first. Skipping bin scenarios."
            )
        if len(household_plans) < 1:
            self.log_error(
                "Need 1 household-collection TripPlan with complete staff/vehicle — "
                "seed schedule-setup and customer-masters first. Skipping household scenario."
            )

        summary = []
        if len(bin_plans) >= 1:
            summary.append(self._run_proceed_next_trip_scenario(bin_plans[0], today, is_household=False))
        if len(household_plans) >= 1:
            summary.append(self._run_proceed_next_trip_scenario(household_plans[0], today, is_household=True))
        if len(bin_plans) >= 2:
            summary.append(self._run_pending_request_scenario(bin_plans[1], today))
        if len(bin_plans) >= 3:
            summary.append(self._run_rejected_request_scenario(bin_plans[2], today))

        self.log("---Re-Trip demo scenarios seeded: " + "; ".join(s for s in summary if s) + "---")

    # ------------------------------------------------------------------
    def _eligible_plans(self, collection_type, limit):
        qs = (
            TripPlan.objects.filter(
                is_deleted=False,
                status=TripPlan.Status.ACTIVE,
                approval_status=TripPlan.ApprovalStatus.APPROVED,
                collection_type=collection_type,
            )
            .exclude(
                staff_template_id__in=DEMO_STAFF_TEMPLATE_UNIQUE_IDS,
            )
            
        )
        if collection_type == TripPlan.COLLECTION_TYPE_BIN:
            qs = qs.order_by("-unique_id")
        else:
            qs = qs.order_by("unique_id")

        eligible = []
        for plan in qs:
            if not plan.staff_template_id:
                continue
            # Resolve driver_id and operator_id from the staff_template
            # (both are CharField unique_ids on StaffTemplate, not FKs)
            from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
            tmpl = StaffTemplate.objects.filter(
                unique_id=plan.staff_template_id,
                is_deleted=False,
            ).first()
            if not tmpl:
                continue
            driver_id = tmpl.driver_id
            operator_id = tmpl.operator_id
            if not driver_id or not operator_id:
                continue
            # Check against demo usernames directly
            if driver_id in DEMO_STAFF_USERNAMES or operator_id in DEMO_STAFF_USERNAMES:
                continue
            eligible.append(plan)
        else:
            pass
        return eligible[:limit]

    # ------------------------------------------------------------------
    def _get_or_create_today_assignment(self, plan, today):
        """Not a plain get_or_create: once a scenario below has called
        proceed_to_next_trip()/approve_retrip() on this (plan, today) pair, a
        SECOND assignment — the continuation — legitimately exists for the
        same key, and get_or_create()'s implicit .get() would raise
        MultipleObjectsReturned on the next seed run. Treat the oldest row as
        'the' assignment for this scenario and only create when none exists
        yet — creation itself is delegated to generate_assignment_for_plan,
        the canonical assignment+stop-cloning path, so this demo gets exactly
        the same stops a real auto-assign run would produce.

        A household plan's "today" assignment may already exist here, made
        by DailyTripAssignmentSeeder's generic week-of-history sweep before
        CustomerCreationSeeder ran (schedule-operations seeds before
        customer-masters) — so it was cloned with zero household stops.
        sync_daily_assignment_stops_from_plan is get_or_create-based and
        safe to call again, so it's re-run here unconditionally to backfill
        whatever was missed the first time."""
        from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan

        existing = (
            DailyTripAssignment.objects.filter(trip_plan_id=plan, trip_date=today, is_deleted=False)
            .order_by("created_at")
            .first()
        )
        if existing is not None:
            sync_daily_assignment_stops_from_plan(existing)
            return existing, False

        assignment, created, _cp_created = generate_assignment_for_plan(plan, today)
        if created:
            assignment.approval_status = DailyTripAssignment.APPROVAL_APPROVED
            assignment.remarks = REMARKS
            assignment.save(update_fields=["approval_status", "remarks", "updated_at"])
        return assignment, created

    def _mark_in_progress(self, assignment, today):
        assignment.mark_started(at=timezone.localtime() - timedelta(minutes=5))

    # ------------------------------------------------------------------
    def _partially_collect_bin_stops(self, assignment):
        """Collect the first N stops (by sequence), leave the rest Pending.
        Returns (collected_count, pending_stop_unique_ids)."""
        operator = assignment.staff_template.operator_id if assignment.staff_template else None
        stops = list(
            DailyTripCollectionPoint.objects.filter(trip_assignment_id=assignment.unique_id, is_deleted=False)
            .order_by("sequence")
        )
        split = _split_for_partial_completion(len(stops))
        if split is None:
            return 0, []
        collected_count, _pending_count = split

        pending_ids = []
        for index, stop in enumerate(stops):
            if index < collected_count:
                if stop.is_collected:
                    continue
                weight = stop.bin.bin_capacity if stop.bin_id else 50
                if operator:
                    stop.mark_collected(weight_kg=min(weight, 150), collected_by=operator)
            else:
                pending_ids.append(stop.unique_id)
        return collected_count, pending_ids

    def _partially_collect_household_stops(self, assignment):
        """Collect the first N household stops (by sequence, via a real
        WasteCollection row, so the post_save signal chain runs), leave the
        rest Pending. Returns collected_count."""
        stops = list(
            DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment.unique_id, is_deleted=False)
            .order_by("sequence")
        )
        split = _split_for_partial_completion(len(stops))
        if split is None:
            return 0
        collected_count, _pending_count = split

        made = 0
        for index, stop in enumerate(stops[:collected_count]):
            if stop.is_collected:
                continue
            if WasteCollection.objects.filter(
                customer=stop.customer_id, trip_assignment_id=assignment
            ).exists():
                continue
            wet, dry, mixed, sanitary = WASTE_PRESETS[index % len(WASTE_PRESETS)]
            WasteCollection.objects.create(
                customer=stop.customer_id,
                trip_assignment_id=assignment,
                collection_date=assignment.trip_date,
                wet_waste=wet,
                dry_waste=dry,
                mixed_waste=mixed,
                sanitary_waste=sanitary,
                # post_save signal marks `stop` collected + syncs the log.
            )
            made += 1
        return made

    # ------------------------------------------------------------------
    def _run_proceed_next_trip_scenario(self, plan, today, *, is_household):
        assignment, _created = self._get_or_create_today_assignment(plan, today)
        if assignment.status in (DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED):
            return f"{assignment.unique_id} already proceeded"

        self._mark_in_progress(assignment, today)

        if is_household:
            collected = self._partially_collect_household_stops(assignment)
            if collected == 0 and not assignment.has_pending_stops():
                return f"{assignment.unique_id} has no household stops to demo"
            actor = plan.supervisor_id or plan.staff_template_id.operator_id
            _request, continuation = retrip_service.proceed_to_next_trip(
                assignment, actor=actor, collection_point_ids=None, remarks=REMARKS,
            )
        else:
            collected, pending_ids = self._partially_collect_bin_stops(assignment)
            if not pending_ids:
                return f"{assignment.unique_id} has no pending collection points to demo"
            actor = plan.supervisor_id or plan.staff_template_id.operator_id
            _request, continuation = retrip_service.proceed_to_next_trip(
                assignment, actor=actor, collection_point_ids=pending_ids, remarks=REMARKS,
            )

        kind = "household" if is_household else "bin"
        return f"{assignment.unique_id} ({kind}, {collected} collected) -> continuation {continuation.unique_id}"

    def _run_pending_request_scenario(self, plan, today):
        assignment, _created = self._get_or_create_today_assignment(plan, today)
        if TripRetripRequest.objects.filter(
            assignment_id=assignment.unique_id, status="Pending"
        ).exists():
            return f"{assignment.unique_id} already has a pending Re-Trip request"
        if assignment.status in (DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED):
            return f"{assignment.unique_id} already closed — skip pending-request demo"

        self._mark_in_progress(assignment, today)
        collected, pending_ids = self._partially_collect_bin_stops(assignment)
        if not pending_ids:
            return f"{assignment.unique_id} has no pending collection points to demo"

        driver = assignment.staff_template.driver_id if assignment.staff_template else None
        retrip_service.request_retrip(assignment, requested_by=driver, reason=REMARKS)
        return f"{assignment.unique_id} (bin, {collected} collected) -> Pending Re-Trip request raised"

    def _run_rejected_request_scenario(self, plan, today):
        assignment, _created = self._get_or_create_today_assignment(plan, today)
        if TripRetripRequest.objects.filter(
            assignment_id=assignment.unique_id, status="Rejected"
        ).exists():
            return f"{assignment.unique_id} already has a rejected Re-Trip request"
        if assignment.status in (DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED):
            return f"{assignment.unique_id} already closed — skip rejected-request demo"

        self._mark_in_progress(assignment, today)
        collected, pending_ids = self._partially_collect_bin_stops(assignment)
        if not pending_ids:
            return f"{assignment.unique_id} has no pending collection points to demo"

        driver = assignment.staff_template.driver_id if assignment.staff_template else None
        supervisor = plan.supervisor_id
        request = retrip_service.request_retrip(assignment, requested_by=driver, reason=REMARKS)
        retrip_service.reject_retrip(request, reviewed_by=supervisor, remarks="Please finish the remaining stops today.")
        return f"{assignment.unique_id} (bin, {collected} collected) -> Rejected Re-Trip request"
