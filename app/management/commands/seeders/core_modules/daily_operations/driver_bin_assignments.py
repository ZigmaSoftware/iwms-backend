"""Exactly TWO bin-collection assignments for `driver_user`, split by waste
stream: a 19-collection-point Wet Waste round and a 5-collection-point Dry
Waste round.

Replaces the old `driver_extra_collection_points` seeder (deleted — no more
single ad-hoc collection-point seeders) and folds the old
`driver_bin_only`/`driver_palakkad_trips` "retire household/bulk" cleanup for
one more thing: any stray bin-collection TripPlan for driver_user that this
seeder didn't itself create (e.g. `DRIVER-WET-VEHICLE-01-*`, left over from
an earlier ad-hoc run) is retired the same way household/bulk plans are —
`driver_user` should have exactly these two bin-collection TripPlans, nothing
else.

Requires `driver-trips` to have already run first — needs the
company/project/district/city/zone/ward masters and driver_user's
StaffTemplate; also reuses `DRIVERUSER-PAL-BIN-01` (created by that seeder)
as the Wet Waste assignment rather than creating a third plan.

Idempotent — safe to re-run. Re-running replaces each assignment's stop set
wholesale (clears then rebuilds) so the plan always ends up with exactly the
19 (or 5) CPs below, never a growing mixed pile from earlier runs.
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.assets.bins import BinType, Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone


COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Palakkad BP"
DRIVER_USERNAME = "driver_user"

WET_PLAN_DISPLAY_CODE = "DRIVERUSER-PAL-BIN-01"   # the pre-existing bin plan
DRY_PLAN_DISPLAY_CODE = "DRIVERUSER-PAL-BIN-02"   # new second plan

# 19 Wet Waste collection points for assignment 1.
WET_POINTS = [
    ("CP-PAL-WET-01", "10.7897", "76.6578"),
    ("CP-PAL-WET-02", "10.7923", "76.6604"),
    ("CP-PAL-WET-03", "10.7927", "76.6608"),
    ("CP-PAL-WET-04", "10.7931", "76.6612"),
    ("CP-PAL-WET-05", "10.7935", "76.6616"),
    ("CP-PAL-WET-06", "10.7939", "76.6620"),
    ("CP-PAL-WET-07", "10.7943", "76.6624"),
    ("CP-PAL-WET-08", "10.7947", "76.6628"),
    ("CP-PAL-WET-09", "10.7951", "76.6632"),
    ("CP-PAL-WET-10", "10.7955", "76.6636"),
    ("CP-PAL-WET-11", "10.7959", "76.6640"),
    ("CP-PAL-WET-12", "10.7963", "76.6644"),
    ("CP-PAL-WET-13", "10.7967", "76.6648"),
    ("CP-PAL-WET-14", "10.7971", "76.6652"),
    ("CP-PAL-WET-15", "10.7975", "76.6656"),
    ("CP-PAL-WET-16", "10.7979", "76.6660"),
    ("CP-PAL-WET-17", "10.7983", "76.6664"),
    ("CP-PAL-WET-18", "10.7987", "76.6668"),
    ("CP-PAL-WET-19", "10.7991", "76.6672"),
]

# 5 Dry Waste collection points for assignment 2.
DRY_POINTS = [
    ("CP-PAL-DRY-01", "10.7995", "76.6676"),
    ("CP-PAL-DRY-02", "10.7999", "76.6680"),
    ("CP-PAL-DRY-03", "10.8003", "76.6684"),
    ("CP-PAL-DRY-04", "10.8007", "76.6688"),
    ("CP-PAL-DRY-05", "10.8011", "76.6692"),
]


class DriverBinAssignmentsSeeder(BaseSeeder):
    name = "driver_bin_assignments"

    def run(self):
        ctx = self._resolve_context()
        if ctx is None:
            return

        wet_type = self._waste_type(ctx, "Wet Waste")
        dry_type = self._waste_type(ctx, "Dry Waste")
        if wet_type is None or dry_type is None:
            return

        wet_plan = ctx["wet_plan"]
        dry_plan = self._seed_dry_plan(ctx)

        # Fix each plan's own waste-type designation — both plans still
        # carried `waste_type_id` = Dry Waste (a leftover from the original
        # mixed-type seeder that this seeder replaces), and the wet plan's
        # `waste_types` M2M still had all three types on it.
        self._set_plan_waste_type(wet_plan, wet_type)
        self._set_plan_waste_type(dry_plan, dry_type)

        wet_points = self._seed_collection_points(ctx, WET_POINTS)
        wet_bins = self._seed_bins(ctx, wet_points, wet_type)
        self._replace_stops(ctx, wet_plan, wet_bins)

        dry_points = self._seed_collection_points(ctx, DRY_POINTS)
        dry_bins = self._seed_bins(ctx, dry_points, dry_type)
        self._replace_stops(ctx, dry_plan, dry_bins)

        self._retire_stray_bin_plans(ctx, keep_plan_ids={wet_plan.unique_id, dry_plan.unique_id})
        self._resync_assignment_waste_types(wet_plan, wet_type)
        self._resync_assignment_waste_types(dry_plan, dry_type)

        from app.management.commands.generate_daily_trips import run_for_date
        today = timezone.localdate()
        result = run_for_date(today, force=True)
        self.log(f"Regenerated assignments for {today}: {result}")

        self.log(
            f"---driver_user bin assignments ready: "
            f"{wet_plan.display_code} (Wet Waste, {len(wet_bins)} CPs), "
            f"{dry_plan.display_code} (Dry Waste, {len(dry_bins)} CPs)---"
        )

    # ------------------------------------------------------------------
    def _set_plan_waste_type(self, plan, waste_type):
        plan.waste_type_id = waste_type
        plan.waste_type_ids = []
        plan.save(update_fields=["waste_type_id", "waste_type_ids"])
        plan.waste_types.set([waste_type])

    # ------------------------------------------------------------------
    def _resync_assignment_waste_types(self, plan, waste_type):
        """`DailyTripAssignment.waste_type_ids` is a snapshot taken from the
        plan only at assignment-creation time (see generate_daily_trips.py)
        — it's never re-read from the plan afterward. An assignment
        generated before this seeder's `_set_plan_waste_type` fix would
        otherwise keep showing the old (wrong) waste type on the driver's
        home screen forever. Re-stamp every one of this plan's
        assignments — cheap, and correct regardless of when it was
        generated.
        """
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment

        updated = DailyTripAssignment.objects.filter(
            trip_plan_id=plan, is_deleted=False,
        ).update(waste_type_ids=[waste_type.unique_id])
        if updated:
            self.log(f"Re-stamped waste type on {updated} assignment(s) for {plan.display_code}.")

    # ------------------------------------------------------------------
    def _resolve_context(self):
        company = Company.objects.filter(name=COMPANY_NAME, is_deleted=False).first()
        if not company:
            self.log(f"Company '{COMPANY_NAME}' not found — run the superadmin seeders first.")
            return None

        project = Project.objects.filter(
            name=PROJECT_NAME, company_id=company, is_deleted=False
        ).first()
        if not project:
            self.log(f"Project '{PROJECT_NAME}' not found under {COMPANY_NAME}.")
            return None

        scope = {"company_id": company, "project_id": project, "is_deleted": False}
        district = District.objects.filter(**scope).first()
        city = City.objects.filter(**scope).first()
        zone = Zone.objects.filter(**scope).first()
        ward = Ward.objects.filter(**scope).first()

        missing = [
            label for label, value in (
                ("district", district), ("city", city), ("zone", zone), ("ward", ward),
            ) if not value
        ]
        if missing:
            self.log(f"Missing {PROJECT_NAME} masters: {', '.join(missing)}. Seed masters first.")
            return None

        driver = Staffcreation.objects.filter(username=DRIVER_USERNAME, is_deleted=False).first()
        if not driver:
            self.log(f"'{DRIVER_USERNAME}' not found — run the user-creations seeders first.")
            return None

        wet_plan = TripPlan.objects.filter(
            company_id=company, project_id=project,
            display_code=WET_PLAN_DISPLAY_CODE, is_deleted=False,
        ).first()
        if not wet_plan:
            self.log(
                f"TripPlan '{WET_PLAN_DISPLAY_CODE}' not found — run the "
                f"'driver-trips' seed group first."
            )
            return None

        return {
            "company": company, "project": project,
            "district": district, "city": city, "zone": zone, "ward": ward,
            "driver": driver, "wet_plan": wet_plan,
        }

    def _waste_type(self, ctx, name):
        waste_type = WasteType.objects.filter(
            company_id=ctx["company"], project_id=ctx["project"],
            waste_type_name=name, is_deleted=False,
        ).first()
        if not waste_type:
            self.log(f"Waste type '{name}' not found under {PROJECT_NAME}. Seed waste types first.")
        return waste_type

    # ------------------------------------------------------------------
    def _seed_dry_plan(self, ctx):
        wet_plan = ctx["wet_plan"]
        plan, created = TripPlan.objects.update_or_create(
            company_id=ctx["company"],
            project_id=ctx["project"],
            display_code=DRY_PLAN_DISPLAY_CODE,
            defaults={
                "district_id": ctx["district"],
                "city_id": ctx["city"],
                "zone_id": ctx["zone"],
                "staff_template_id": wet_plan.staff_template_id,
                "vehicle_id": wet_plan.vehicle_id,
                "supervisor_id": wet_plan.supervisor_id,
                "waste_type_id": wet_plan.waste_type_id,
                "property_id": wet_plan.property_id,
                "sub_property_id": wet_plan.sub_property_id,
                "collection_type": TripPlan.COLLECTION_TYPE_BIN,
                "trip_trigger_weight_kg": 800,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": wet_plan.scheduled_time,
                "status": TripPlan.Status.ACTIVE,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "is_auto_assign": True,
                "repeat_days": [],
                "is_active": True,
                "is_deleted": False,
            },
        )
        plan.wards.set([ctx["ward"]])
        self.log(f"TripPlan {'created' if created else 'updated'}: {plan.unique_id} [{DRY_PLAN_DISPLAY_CODE}]")
        return plan

    # ------------------------------------------------------------------
    def _seed_collection_points(self, ctx, points_spec):
        points = []
        created = 0
        for cp_name, lat, lng in points_spec:
            cp, was_created = Collection_point.objects.update_or_create(
                company_id=ctx["company"],
                project_id=ctx["project"],
                cp_name=cp_name,
                defaults={
                    "state_id": ctx["district"].state_id,
                    "city_id": ctx["city"],
                    "district_id": ctx["district"],
                    "zone_id": ctx["zone"],
                    "collection_type": Collection_point.COLLECTION_TYPE_BIN,
                    "latitude": lat,
                    "longitude": lng,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            cp.wards.set([ctx["ward"]])
            points.append(cp)
            created += int(was_created)
        self.log(f"Collection points ready: {len(points)} ({created} created).")
        return points

    # ------------------------------------------------------------------
    def _seed_bins(self, ctx, points, waste_type):
        bins = []
        created = 0
        for cp in points:
            bin_name = f"{cp.cp_name} {waste_type.waste_type_name}"
            bin_obj, was_created = Bins.objects.update_or_create(
                company_id=ctx["company"],
                project_id=ctx["project"],
                collection_point_id=cp,
                bin_name=bin_name,
                defaults={
                    "district_id": ctx["district"],
                    "city_id": ctx["city"],
                    "zone_id": ctx["zone"],
                    "ward_id": ctx["ward"],
                    "wastetype_id": waste_type,
                    "bin_capacity": 240,
                    "bin_type": BinType.MEDIUM,
                    "bin_image": "",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            bins.append(bin_obj)
            created += int(was_created)
        self.log(f"Bins ready ({waste_type.waste_type_name}): {len(bins)} ({created} created).")
        return bins

    # ------------------------------------------------------------------
    def _replace_stops(self, ctx, plan, bins):
        """Wipe ALL of this plan's existing stops and rebuild from scratch —
        so a re-run always leaves the plan with exactly these CPs, in this
        exact sequence order, no matter what was on it before (including a
        corrupted/duplicated stop set from an unrelated daily-generation
        run — `sequence` is uniquely constrained per trip_plan_id, so any
        stale row occupying a sequence number this rebuild wants to use
        must be gone first, not just the ones for bins no longer on the
        plan).

        Hard-deleted, not soft-deleted: a soft-deleted stop still holds its
        `sequence` value under that constraint. Nothing else references a
        TripPlanCollectionPoint by FK with PROTECT — the daily child tables
        (DailyTripCollectionPoint) clone its data rather than pointing back
        at it — so this is safe.
        """
        TripPlanCollectionPoint.objects.filter(trip_plan_id=plan).delete()

        for sequence, bin_obj in enumerate(bins, start=1):
            TripPlanCollectionPoint.objects.create(
                trip_plan_id=plan,
                collection_point_id=bin_obj.collection_point_id,
                bin_id=bin_obj,
                company_id=ctx["company"],
                project_id=ctx["project"],
                collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                sequence=sequence,
                zone_id=ctx["zone"],
                ward_id=ctx["ward"],
                is_active=True,
                is_deleted=False,
            )
        self.log(f"Stops on {plan.display_code}: {len(bins)} (rebuilt from scratch).")
        self._prune_stale_daily_stops(plan, bins)

    # ------------------------------------------------------------------
    def _prune_stale_daily_stops(self, plan, bins):
        """`sync_daily_assignment_stops_from_plan` (the post_save signal /
        `run_for_date` safety net) only ADDS bin stops to an already-cloned
        DailyTripAssignment — it never removes ones for a bin no longer on
        the plan. So a plan rebuild alone leaves any assignment generated
        BEFORE this run still showing the old (now off-plan) bins alongside
        the new ones. Prune those here — anything never collected, on any
        of this plan's assignments — so today's (and any future) assignment
        ends up with exactly the current bin set. Collected stops are left
        alone; they're real audit history, not stale seed data.
        """
        from app.models.schedule_masters.daily_trip_collection_point import (
            DailyTripCollectionPoint,
        )

        deleted, _ = DailyTripCollectionPoint.objects.filter(
            trip_assignment_id__trip_plan_id=plan,
            is_collected=False,
        ).exclude(bin_id__in=bins).delete()
        if deleted:
            self.log(f"Pruned {deleted} stale (never-collected) daily stop(s) on {plan.display_code}.")

    # ------------------------------------------------------------------
    def _retire_stray_bin_plans(self, ctx, keep_plan_ids):
        """Any bin-collection TripPlan for driver_user that isn't one of the
        two this seeder manages — leftover from an earlier ad-hoc run —
        gets deactivated (not hard-deleted: real DailyTripAssignment /
        BinCollectionEvent history may reference it via PROTECT) and its
        pending assignments cancelled, same treatment as the retired
        household/bulk plans.
        """
        # Matched by driver, not by company/project — a stray plan can carry
        # a mismatched company/project (seen in practice: a generic stock
        # seeder created a bin-collection TripPlan under a different
        # company whose StaffTemplate nonetheless points `driver_id` at
        # driver_user's real Staffcreation row). driver_user should have
        # no bin-collection plan this seeder doesn't itself manage, in any
        # company.
        stray_plans = TripPlan.objects.filter(
            staff_template_id__driver_id=ctx["driver"],
            collection_type=TripPlan.COLLECTION_TYPE_BIN,
            is_deleted=False,
        ).exclude(unique_id__in=keep_plan_ids)

        stray_count = stray_plans.count()
        if not stray_count:
            return

        stray_plan_ids = list(stray_plans.values_list("unique_id", flat=True))
        stray_plans.update(is_active=False, status=TripPlan.Status.INACTIVE)

        today = timezone.localdate()
        assignments = DailyTripAssignment.objects.filter(
            trip_plan_id__in=stray_plan_ids,
            trip_date__gte=today,
            is_deleted=False,
        ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)

        cancelled = 0
        for assignment in assignments:
            if assignment.status == DailyTripAssignment.STATUS_COMPLETED:
                continue
            assignment.status = DailyTripAssignment.STATUS_CANCELLED
            assignment.save(update_fields=["status", "updated_at"])
            cancelled += 1

        self.log(
            f"Retired {stray_count} stray bin-collection TripPlan(s) "
            f"({', '.join(stray_plan_ids)}) and cancelled {cancelled} "
            f"pending assignment(s)."
        )
