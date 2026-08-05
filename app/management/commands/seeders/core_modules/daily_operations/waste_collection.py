from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.customers.wastecollection import WasteCollection
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.schedule_masters.trip_plan import TripPlan

# (wet, dry, mixed, sanitary) kg presets — cycled through for varied,
# reproducible data.
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


def _deterministic_outcome(sequence, day_offset):
    """~85% Collected, rest split Not Available / Collect Later — a pure
    function of (sequence, day_offset), so re-seeding stays idempotent."""
    key = (sequence + day_offset) % 10
    if key == 0:
        return "NOT_AVAILABLE"
    if key == 5:
        return "COLLECT_LATER"
    return "COLLECTED"


class WasteCollectionSeeder(BaseSeeder):
    """For every household DailyTripAssignment created by
    DailyTripAssignmentSeeder, resolve each of its (signal-created)
    DailyTripHouseholdCollection stops as either Collected (creating a
    WasteCollection row, which the sync_household_collection_on_waste_save
    signal then reflects onto both the household stop and the trip's
    DailyTripLog) or Not Available / Collect Later (updating the household
    stop directly, no WasteCollection row).

    Today is excluded so it stays available, unresolved, for
    RetripDemoSeeder's dedicated partial-completion scenarios — see that
    seeder's docstring.

    Household DailyTripAssignments are created by DailyTripAssignmentSeeder,
    which runs in the "schedule-operations" group — BEFORE "customer-masters"
    seeds any CustomerCreation rows. Since household stops are resolved
    against whatever customers exist at assignment-creation time, those
    assignments are cloned with zero household stops on a fresh `seed all`
    run. `sync_daily_assignment_stops_from_plan` is get_or_create-based and
    safe to call again, so this seeder re-runs it per assignment first —
    now that customers exist, it backfills the stops that were missed.
    """

    name = "waste_collection"

    def run(self):
        from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan

        assignments = list(
            DailyTripAssignment.objects.filter(
                is_deleted=False,
                trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            )
            .exclude(trip_date=timezone.localdate())
            .order_by("trip_date")
        )
        if not assignments:
            self.log("No household DailyTripAssignments found — run DailyTripAssignmentSeeder first.")
            return

        today = timezone.localdate()
        backfilled_stops = 0
        created_count = 0
        updated_count = 0
        for assignment in assignments:
            backfilled_stops += sync_daily_assignment_stops_from_plan(assignment)
            day_offset = (today - assignment.trip_date).days
            stops = DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            ).select_related("customer_id").order_by("sequence")

            for stop in stops:
                if stop.is_collected:
                    continue

                outcome = _deterministic_outcome(stop.sequence, day_offset)
                if outcome == "COLLECTED":
                    if WasteCollection.objects.filter(
                        customer=stop.customer_id, trip_assignment_id=assignment
                    ).exists():
                        continue
                    wet, dry, mixed, sanitary = WASTE_PRESETS[(stop.sequence + day_offset) % len(WASTE_PRESETS)]
                    WasteCollection.objects.create(
                        customer=stop.customer_id,
                        trip_assignment_id=assignment,
                        collection_date=assignment.trip_date,
                        wet_waste=wet,
                        dry_waste=dry,
                        mixed_waste=mixed,
                        sanitary_waste=sanitary,
                        # total_quantity is auto-calculated in WasteCollection.save();
                        # the post_save signal marks `stop` collected and syncs the
                        # trip's DailyTripLog automatically.
                    )
                    created_count += 1
                else:
                    reason = (
                        "Customer unavailable today."
                        if outcome == "NOT_AVAILABLE"
                        else "Requested collection later today."
                    )
                    stop.status = (
                        DailyTripHouseholdCollection.STATUS_MISSED
                        if outcome == "NOT_AVAILABLE"
                        else DailyTripHouseholdCollection.STATUS_COLLECT_LATER
                    )
                    stop.status_reason = reason
                    stop.is_collected = False
                    stop.save(update_fields=["status", "status_reason", "is_collected", "updated_at"])
                    updated_count += 1

        self.log(
            f"---WasteCollection seeded | backfilled_stops={backfilled_stops} | created={created_count} | "
            f"household stops marked missed/collect-later={updated_count}---"
        )
