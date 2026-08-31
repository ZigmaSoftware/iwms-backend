"""Exactly TWO bin-collection DailyTripAssignments for `driver_user`, split
by waste stream — 10 Wet Waste collection points and 10 Dry Waste collection
points — supervised by `supervisor_user`.

A THIRD plan — one household-collection TripPlan reusing existing Palakkad
BP customers — is added by the sibling seeder `driver_household_trip.py`
(added on request: driver_user needs a household trip to exercise the
mobile app's household collection flow, alongside these bin trips, not
instead of them). That seeder must run AFTER this one — see
`HOUSEHOLD_PLAN_DISPLAY_CODE` import below, used so `_purge_foreign_plans`/
`_assert_exactly_two_plans` here know to leave it alone rather than treating
it as a stray foreign plan.

Builds the whole chain from scratch (self-contained — does NOT depend on the
retired `driver_palakkad_trips`/`driver_bin_assignments` seeders having run):

    driver_user / supervisor_user (repinned to Blue Planet / Palakkad BP)
        └─ StaffTemplate (driver_user + operator_user)
             └─ TripPlan  x2   (bin_collection: Wet, Dry) — supervisor_id = supervisor_user
                  └─ 10 CollectionPoints + 10 Bins each (Wet / Dry WasteType)
                       └─ TripPlanCollectionPoint stops
                            └─ run_for_date(force=True)
                                 └─ DailyTripAssignment
                                      └─ DailyTripCollectionPoint (fresh, Pending, collectible)

Why self-contained: `driver_palakkad_trips.py`/`driver_bin_assignments.py`
were removed from the seed pipeline on request (driver_user should have zero
trips out of the box — since revised, see the household note above). This
seeder is the one now wired into `schedule-operations`, and must not
silently do nothing if those retired seeders were never run — it repins
driver_user/supervisor_user itself, exactly like `driver_palakkad_trips.py`
used to.

Company/project scope: `AuthUserSeeder` creates driver_user/operator_user
under whatever company/project sorts first in the DB (no name filter), which
is almost never Blue Planet/Palakkad BP — where `BluePlanetSeeder` (run
earlier, in the `superadmin` group) creates the district/city/zone/ward/
vehicle/waste-types this seeder needs. So driver_user's/operator_user's own
`Staffcreation.company_id`/`project_id` are force-repinned to Blue Planet/
Palakkad BP here, same as the retired seeder did.

`supervisor_user` circular-dependency note: `SupervisorUserSeeder` only
creates that login once `driver_user` already has a trip assignment for
today — but that assignment is exactly what THIS seeder creates, and it
needs `supervisor_user` to already exist to set as the trip plan's
supervisor. Rather than depend on seed-group ordering to break that cycle,
this seeder get-or-creates a minimal `supervisor_user` login itself if
missing (same fields `SupervisorUserSeeder` sets) — `SupervisorUserSeeder`
running before or after this one is then just an idempotent update either
way, never a hard dependency.

Idempotent: get_or_create / update_or_create throughout, safe to re-run.
Re-running replaces each plan's stop set wholesale (clears then rebuilds) so
a plan always ends up with exactly its 10 CPs, never a growing/mixed pile.
"""

import math

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.core_modules.daily_operations.driver_household_trip import (
    HOUSEHOLD_PLAN_DISPLAY_CODE,
)

from app.models.assets.bins import BinType, Bins
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType


COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Palakkad BP"
DRIVER_USERNAME = "driver_user"
OPERATOR_USERNAME = "operator_user"
SUPERVISOR_USERNAME = "supervisor_user"

WET_PLAN_DISPLAY_CODE = "DRIVERUSER-PAL-WETBIN-01"
DRY_PLAN_DISPLAY_CODE = "DRIVERUSER-PAL-DRYBIN-01"

def _scatter(base_lat, base_lon, index, spread=0.012):
    """Deterministic pseudo-random offset around an anchor point, so seeded
    collection points land scattered across real streets on a map instead
    of walking in a single straight line (a fixed per-index increment
    produces exactly that — a line of pins)."""
    angle = (index * 137.508) % 360  # golden-angle spacing — avoids clustering
    radius = spread * (0.35 + 0.65 * ((index * 0.618) % 1))
    d_lat = radius * math.cos(math.radians(angle))
    d_lon = radius * math.sin(math.radians(angle))
    return f"{base_lat + d_lat:.6f}", f"{base_lon + d_lon:.6f}"


# 10 Wet Waste collection points, scattered around central Palakkad.
WET_POINTS = [
    (f"CP-PAL-WETBIN-{idx:02d}", *_scatter(10.7867, 76.6548, idx))
    for idx in range(1, 11)
]

# 10 Dry Waste collection points, scattered around a nearby Palakkad anchor
# (offset from the wet-waste anchor so the two waste streams cover
# different parts of town rather than overlapping).
DRY_POINTS = [
    (f"CP-PAL-DRYBIN-{idx:02d}", *_scatter(10.7950, 76.6650, idx + 20))
    for idx in range(1, 11)
]


class DriverWetDryBinTripsSeeder(BaseSeeder):
    name = "driver_wet_dry_bin_trips"

    def run(self):
        ctx = self._resolve_context()
        if ctx is None:
            return

        wet_plan = self._seed_plan(
            ctx, WET_PLAN_DISPLAY_CODE, ctx["wet_type"], scheduled_time="07:00"
        )
        dry_plan = self._seed_plan(
            ctx, DRY_PLAN_DISPLAY_CODE, ctx["dry_type"], scheduled_time="09:00"
        )

        wet_points = self._seed_collection_points(ctx, WET_POINTS)
        wet_bins = self._seed_bins(ctx, wet_points, ctx["wet_type"])
        self._replace_stops(ctx, wet_plan, wet_bins)

        dry_points = self._seed_collection_points(ctx, DRY_POINTS)
        dry_bins = self._seed_bins(ctx, dry_points, ctx["dry_type"])
        self._replace_stops(ctx, dry_plan, dry_bins)

        self._resync_assignment_waste_types(wet_plan, ctx["wet_type"])
        self._resync_assignment_waste_types(dry_plan, ctx["dry_type"])

        # Self-healing: driver_user must end up with EXACTLY these two bin
        # plans plus (if driver_household_trip.py has already run) its one
        # household plan. Anything else on their StaffTemplate came from a
        # seeder that shouldn't have touched them — the generic TripPlanSeeder
        # (which cycles every active StaffTemplate across its ward/panchayat
        # plans unless EXCLUDED_DRIVER_USERNAMES filters them out), or one of
        # the retired driver_palakkad_trips/driver_bin_only/
        # driver_bin_assignments seeders on an older branch. Purge them here
        # rather than relying on that exclusion surviving every future merge.
        #
        # Matched by display_code, not existence-checked via a DB query, so
        # this works whether driver_household_trip.py ran before this seeder
        # (its plan already exists — keep it) or hasn't run yet (no plan with
        # that code exists yet — the `.exclude(...)` below is simply a no-op,
        # and that seeder creates its own plan fresh when it runs next).
        keep = {wet_plan.pk, dry_plan.pk}
        keep |= set(
            TripPlan.objects.filter(
                staff_template_id__driver_id=ctx["driver"],
                display_code=HOUSEHOLD_PLAN_DISPLAY_CODE,
            ).values_list("pk", flat=True)
        )
        self._purge_foreign_plans(ctx, keep=keep)

        from app.management.commands.generate_daily_trips import run_for_date
        today = timezone.localdate()
        result = run_for_date(today, force=True)
        self.log(f"Regenerated assignments for {today}: {result}")

        # `run_for_date` only sets `scheduled_time` when an assignment is first
        # created, so re-seeding never updates already-existing rows. Re-stamp
        # today's assignments so they match the (now distinct) plan times — the
        # scan resolver picks "the active trip" by scheduled time, so two plans
        # sharing 07:00 silently misrouted wet scans to the dry trip.
        self._resync_assignment_scheduled_time(wet_plan, today)
        self._resync_assignment_scheduled_time(dry_plan, today)

        self._report([wet_plan, dry_plan])
        self._assert_exactly_two_plans(ctx)

        self.log(
            f"---driver_user wet/dry bin trips ready: "
            f"{wet_plan.display_code} (Wet Waste, {len(wet_bins)} CPs), "
            f"{dry_plan.display_code} (Dry Waste, {len(dry_bins)} CPs)---"
        )

    # ------------------------------------------------------------------
    def _assert_exactly_two_plans(self, ctx):
        """Fail loudly if driver_user ends up with anything but the wet/dry
        pair plus, optionally, the household plan (see the module docstring —
        only present once driver_household_trip.py has run). Everything
        upstream is meant to guarantee this; an unexpected extra code here
        means some other seeder created plans AFTER _purge_foreign_plans ran,
        which would otherwise only surface as extra trip cards in the app.
        """
        codes = sorted(
            TripPlan.objects.filter(
                staff_template_id__driver_id=ctx["driver"],
            ).values_list("display_code", flat=True)
        )
        allowed = {WET_PLAN_DISPLAY_CODE, DRY_PLAN_DISPLAY_CODE, HOUSEHOLD_PLAN_DISPLAY_CODE}
        unexpected = [c for c in codes if c not in allowed]
        if unexpected:
            raise RuntimeError(
                f"driver_user must have only {sorted(allowed)}, but also has "
                f"{unexpected}. Another seeder is creating trip plans for "
                f"driver_user — check TripPlanSeeder's EXCLUDED_DRIVER_USERNAMES "
                f"and that no retired driver seeder was reintroduced by a merge."
            )

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
        vehicle = VehicleCreation.objects.filter(**scope).first()

        missing = [
            label for label, value in (
                ("district", district), ("city", city), ("zone", zone), ("ward", ward),
                ("vehicle", vehicle),
            ) if not value
        ]
        if missing:
            self.log(f"Missing {PROJECT_NAME} masters: {', '.join(missing)}. Seed superadmin first.")
            return None

        wet_type = WasteType.objects.filter(
            **scope, waste_type_name="Wet Waste",
        ).first()
        dry_type = WasteType.objects.filter(
            **scope, waste_type_name="Dry Waste",
        ).first()
        if not wet_type or not dry_type:
            self.log(f"Wet/Dry WasteType not found under {PROJECT_NAME}. Seed superadmin first.")
            return None

        driver = Staffcreation.objects.filter(username=DRIVER_USERNAME, is_deleted=False).first()
        operator = Staffcreation.objects.filter(username=OPERATOR_USERNAME, is_deleted=False).first()
        if not driver:
            self.log(f"'{DRIVER_USERNAME}' not found — run the user-creations seeders first.")
            return None
        if not operator:
            # StaffTemplate.operator_id is required; fall back to the driver
            # so the merged driver/captain flow still works.
            operator = driver

        supervisor = self._get_or_create_supervisor(driver, company, project)
        if supervisor is None:
            return None

        # AuthUserSeeder creates driver_user/operator_user under WHATEVER
        # company/project happens to sort first in the DB (no name filter) —
        # almost never Blue Planet/Palakkad BP. Repin here (same fix
        # driver_palakkad_trips.py used to apply) so CompanyScopedViewSet
        # doesn't filter this seeder's own trips out of the driver app.
        for staff in {driver, operator, supervisor}:
            if staff.company_id_id != company.unique_id or staff.project_id_id != project.unique_id:
                staff.company_id = company
                staff.project_id = project
                staff.district_id = district
                staff.city_id = city
                staff.zone_id = zone
                staff.ward_id = ward
                # staff_id is scoped per company+project (STF0001-style display
                # ID). Moving to a new tenant scope must re-scope it, otherwise
                # the old value can already belong to another staff in the
                # target scope and violate uniq_staff_id_per_company_project.
                staff.staff_id = None
                staff.save(update_fields=[
                    "company_id", "project_id", "district_id", "city_id",
                    "zone_id", "ward_id", "updated_at",
                ])

        template, created = StaffTemplate.objects.get_or_create(
            company_id=company, project_id=project,
            driver_id=driver, operator_id=operator,
            is_deleted=False,
            defaults={"is_active": True},
        )
        self.log(
            f"StaffTemplate {'created' if created else 'exists'}: "
            f"{template.unique_id} (driver={driver.username}, operator={operator.username})"
        )

        return {
            "company": company, "project": project,
            "district": district, "city": city, "zone": zone, "ward": ward,
            "vehicle": vehicle,
            "driver": driver, "operator": operator, "supervisor": supervisor,
            "template": template, "wet_type": wet_type, "dry_type": dry_type,
        }

    # ------------------------------------------------------------------
    def _get_or_create_supervisor(self, driver, company, project):
        """Same minimal login `SupervisorUserSeeder` creates — duplicated
        (not imported/called) because that seeder's own `run()` bails out
        before creating anything if `driver_user` has no trip assignment
        yet, which is exactly the state this seeder runs in on a fresh DB.
        Whichever of the two seeders runs first creates the login; the
        other just updates the existing row (both are get_or_create/
        update_or_create based) — no conflict either order.
        """
        existing = Staffcreation.objects.filter(
            username=SUPERVISOR_USERNAME, is_deleted=False
        ).first()
        if existing:
            return existing

        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            self.log("UserType 'staff' missing — seed role-assigns first.")
            return None
        role, _ = StaffUserType.objects.get_or_create(
            name="Company Supervisor",
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )

        supervisor, created = Staffcreation.objects.get_or_create(
            username=SUPERVISOR_USERNAME,
            defaults={
                "employee_name": "Supervisor User",
                "password": "Supervisor123",
                "user_type_id": staff_type,
                "staffusertype_id": role,
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
                "is_superuser": False,
                "login_enabled": True,
                "approval_status": Staffcreation.APPROVAL_APPROVED,
            },
        )
        self.log(f"{'Created' if created else 'Found'} '{SUPERVISOR_USERNAME}' login.")
        return supervisor

    # ------------------------------------------------------------------
    def _seed_plan(self, ctx, display_code, waste_type, scheduled_time="07:00"):
        plan, created = TripPlan.objects.update_or_create(
            company_id=ctx["company"],
            project_id=ctx["project"],
            display_code=display_code,
            defaults={
                "district_id": ctx["district"],
                "city_id": ctx["city"],
                "zone_id": ctx["zone"],
                "staff_template_id": ctx["template"],
                "vehicle_id": ctx["vehicle"],
                "supervisor_id": ctx["supervisor"],
                "waste_type_id": waste_type,
                "waste_type_ids": [],
                "collection_type": TripPlan.COLLECTION_TYPE_BIN,
                "trip_trigger_weight_kg": 800,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": scheduled_time,
                "status": TripPlan.Status.ACTIVE,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "is_auto_assign": True,
                # Empty repeat_days means "no scheduled weekday" — generation
                # must be forced (see run_for_date(force=True) below).
                "repeat_days": [],
                "is_active": True,
                "is_deleted": False,
            },
        )
        plan.wards.set([ctx["ward"]])
        plan.waste_types.set([waste_type])
        self.log(
            f"TripPlan {'created' if created else 'updated'}: {plan.unique_id} "
            f"[{display_code}] supervisor={ctx['supervisor'].username}"
        )
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
        so a re-run always leaves the plan with exactly these 10 CPs, in
        this sequence order. Hard-deleted, not soft-deleted: `sequence` is
        uniquely constrained per trip_plan_id, and a soft-deleted row still
        holds its sequence value under that constraint. Nothing else
        references a TripPlanCollectionPoint by FK with PROTECT — the daily
        child tables (DailyTripCollectionPoint) clone its data rather than
        pointing back at it — so this is safe.
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
        """`sync_daily_assignment_stops_from_plan` only ADDS bin stops to an
        already-cloned DailyTripAssignment — it never removes ones for a bin
        no longer on the plan. Prune those here — anything never collected,
        on any of this plan's assignments — so today's (and any future)
        assignment ends up with exactly the current bin set. Collected stops
        are left alone; they're real audit history, not stale seed data.
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
    def _purge_foreign_plans(self, ctx, keep):
        """Hard-delete every TripPlan on driver_user's StaffTemplate that this
        seeder does not own, along with everything hanging off it.

        Deletion order matters: DailyTripAssignment is PROTECTed by
        BinCollectionEvent and DailyTripLog, and TripPlan is PROTECTed by
        DailyTripAssignment — so children must go first or the delete raises
        ProtectedError. Soft-deleting instead is not enough: a cancelled /
        is_deleted plan still shows up as a stale trip card in the app.
        """
        from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
        from app.models.schedule_masters.daily_trip_collection_point import (
            DailyTripCollectionPoint,
        )
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        from app.models.schedule_masters.daily_trip_log import DailyTripLog

        foreign = TripPlan.objects.filter(
            staff_template_id__driver_id=ctx["driver"],
        ).exclude(pk__in=keep)

        codes = list(foreign.values_list("display_code", flat=True))
        if not codes:
            return

        assignments = DailyTripAssignment.objects.filter(trip_plan_id__in=foreign)

        BinCollectionEvent.objects.filter(trip_assignment_id__in=assignments).delete()
        DailyTripLog.objects.filter(trip_assignment_id__in=assignments).delete()
        DailyTripCollectionPoint.objects.filter(trip_assignment_id__in=assignments).delete()
        DailyTripHouseholdCollection.objects.filter(trip_assignment_id__in=assignments).delete()
        assignments.delete()
        foreign.delete()

        self.log(
            f"Purged {len(codes)} trip plan(s) not owned by this seeder "
            f"({', '.join(codes)}) — driver_user keeps only the wet/dry pair."
        )

    # ------------------------------------------------------------------
    def _resync_assignment_waste_types(self, plan, waste_type):
        """`DailyTripAssignment.waste_type_ids` is a snapshot taken from the
        plan only at assignment-creation time — never re-read from the plan
        afterward. Re-stamp every one of this plan's assignments so the
        driver's home screen always reflects this plan's real waste type,
        regardless of when the assignment was generated.
        """
        updated = DailyTripAssignment.objects.filter(
            trip_plan_id=plan, is_deleted=False,
        ).update(waste_type_ids=[waste_type.unique_id])
        if updated:
            self.log(f"Re-stamped waste type on {updated} assignment(s) for {plan.display_code}.")

    # ------------------------------------------------------------------
    def _resync_assignment_scheduled_time(self, plan, trip_date):
        """Re-stamp an already-created assignment's scheduled time.

        `run_for_date` copies `scheduled_time` from the plan only at
        assignment-creation time, so a re-run that changes a plan's time
        leaves existing rows stale. Because the operator scan resolver picks
        today's "active trip" by scheduled_time (earliest with work left),
        stale times can misroute scans (e.g. a wet bin validated against the
        dry trip when both share 07:00).
        """
        updated = DailyTripAssignment.objects.filter(
            trip_plan_id=plan, trip_date=trip_date, is_deleted=False,
        ).update(scheduled_time=plan.scheduled_time)
        if updated:
            self.log(
                f"Re-stamped scheduled_time={plan.scheduled_time} on {updated} "
                f"assignment(s) for {plan.display_code}."
            )

    # ------------------------------------------------------------------
    def _report(self, plans):
        from app.models.schedule_masters.daily_trip_collection_point import (
            DailyTripCollectionPoint,
        )

        today = timezone.localdate()
        for plan in plans:
            assignment = DailyTripAssignment.objects.filter(
                trip_plan_id=plan, trip_date=today, is_deleted=False
            ).order_by("created_at").first()
            if not assignment:
                self.log(f"  !! no assignment generated for {plan.unique_id}")
                continue
            stops = DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            )
            pending = stops.filter(status=DailyTripCollectionPoint.STATUS_PENDING).count()
            self.log(
                f"  {assignment.unique_id} [{plan.display_code}] "
                f"stops={stops.count()} pending/collectible={pending}"
            )
