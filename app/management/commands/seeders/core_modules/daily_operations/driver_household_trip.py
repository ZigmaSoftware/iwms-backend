"""One household-collection DailyTripAssignment for `driver_user`, alongside
(never replacing) the wet/dry bin pair from `driver_wet_dry_bin_trips.py`.

Reuses the Palakkad BP household customers `BluePlanetSeeder` already creates
in `driver_user`'s own ward (Anitha Menon, Suresh Kumar, ...) — no new
CustomerCreation rows. Those customers sit on an existing household TripPlan
too, but that plan's StaffTemplate points at a *different*, seeded-fresh
driver (`bp_pal_driver1`), never `driver_user` — this seeder gives driver_user
its own household TripPlan against the same customers instead of touching
that one.

Builds:

    driver_user's existing StaffTemplate (from driver_wet_dry_bin_trips.py,
    or created here if that seeder hasn't run yet)
         └─ TripPlan (household_collection) — supervisor_id = supervisor_user
              └─ 8 TripPlanCollectionPoint stops, one per reused customer
                   └─ run_for_date(force=True)
                        └─ DailyTripAssignment
                             └─ DailyTripHouseholdCollection (fresh, Pending)

`driver_wet_dry_bin_trips.py`'s `_purge_foreign_plans`/`_assert_exactly_two_plans`
guards were updated to expect this plan alongside the wet/dry pair — see the
`DRIVER_HOUSEHOLD_PLAN_DISPLAY_CODE` import there. Register this seeder in
`seed.py` right after `driver_wet_dry_bin_trips` so a purge from that seeder
running first never deletes what this one is about to (re)create.

Idempotent: get_or_create / update_or_create throughout, safe to re-run.
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.customers.customercreation import CustomerCreation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.staff_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Palakkad BP"
DRIVER_USERNAME = "driver_user"
OPERATOR_USERNAME = "operator_user"
SUPERVISOR_USERNAME = "supervisor_user"

HOUSEHOLD_PLAN_DISPLAY_CODE = "DRIVERUSER-PAL-HOUSEHOLD-01"

# Reuse BluePlanetSeeder's Palakkad household customers (see
# superadmin_masters/blue_planet.py CUSTOMER_DATA["Palakkad BP"]) — matched
# by name since that's the only field this seeder can address them by
# without importing that seeder's private id_no scheme.
CUSTOMER_NAMES_IN_STOP_ORDER = [
    "Anitha Menon",
    "Suresh Kumar",
    "Radhika Nair",
    "Vinod Pillai",
    "Lakshmi Warrier",
    "Rajeev Menon",
    "Deepa Krishnan",
    "Anoop Varma",
]


class DriverHouseholdTripSeeder(BaseSeeder):
    name = "driver_household_trip"

    def run(self):
        ctx = self._resolve_context()
        if ctx is None:
            return

        plan = self._seed_plan(ctx)
        stops = self._seed_stops(ctx, plan)

        from app.management.commands.generate_daily_trips import run_for_date
        today = timezone.localdate()
        result = run_for_date(today, force=True)
        self.log(f"Regenerated assignments for {today}: {result}")

        self._report(plan)
        self.log(
            f"---driver_user household trip ready: {plan.display_code} "
            f"({len(stops)} customer stops)---"
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
        vehicle = VehicleCreation.objects.filter(**scope).first()
        residential_property = Property.objects.filter(
            **scope, property_name="Residential",
        ).first()
        residential_sub_property = SubProperty.objects.filter(
            **scope, sub_property_name="Individual House",
        ).first()

        missing = [
            label for label, value in (
                ("district", district), ("city", city), ("zone", zone),
                ("vehicle", vehicle), ("Residential property", residential_property),
                ("Individual House sub-property", residential_sub_property),
            ) if not value
        ]
        if missing:
            self.log(f"Missing {PROJECT_NAME} masters: {', '.join(missing)}. Seed superadmin first.")
            return None

        wet_type = WasteType.objects.filter(**scope, waste_type_name="Wet Waste").first()
        if not wet_type:
            self.log(f"Wet Waste WasteType not found under {PROJECT_NAME}. Seed superadmin first.")
            return None

        driver = Staffcreation.objects.filter(username=DRIVER_USERNAME, is_deleted=False).first()
        operator = Staffcreation.objects.filter(username=OPERATOR_USERNAME, is_deleted=False).first()
        if not driver:
            self.log(f"'{DRIVER_USERNAME}' not found — run the staff-creations seeders first.")
            return None
        if not operator:
            operator = driver

        ward = Ward.objects.filter(unique_id=driver.ward_id_id, is_deleted=False).first()
        if not ward:
            self.log(f"'{DRIVER_USERNAME}' has no ward assigned — run driver_wet_dry_bin_trips first.")
            return None

        supervisor = self._get_or_create_supervisor(company, project)
        if supervisor is None:
            return None

        customers = list(
            CustomerCreation.objects.filter(
                ward_id=ward, is_deleted=False, is_active=True,
                customer_name__in=CUSTOMER_NAMES_IN_STOP_ORDER,
            )
        )
        if not customers:
            self.log(
                f"No reusable customers found in ward {ward.unique_id} — "
                "run the superadmin (BluePlanetSeeder) group first."
            )
            return None
        # Deterministic stop order matching CUSTOMER_NAMES_IN_STOP_ORDER,
        # rather than whatever order the DB query happens to return.
        by_name = {c.customer_name: c for c in customers}
        customers = [by_name[name] for name in CUSTOMER_NAMES_IN_STOP_ORDER if name in by_name]

        # driver_wet_dry_bin_trips.py creates/repins this same StaffTemplate;
        # get_or_create here so this seeder also works standalone.
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
            "vehicle": vehicle, "residential_property": residential_property,
            "residential_sub_property": residential_sub_property,
            "driver": driver, "operator": operator, "supervisor": supervisor,
            "template": template, "wet_type": wet_type, "customers": customers,
        }

    # ------------------------------------------------------------------
    def _get_or_create_supervisor(self, company, project):
        """Same minimal login driver_wet_dry_bin_trips.py creates —
        duplicated rather than imported so this seeder works standalone; both
        are get_or_create-based, so whichever runs first wins with no
        conflict.
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
    def _seed_plan(self, ctx):
        plan, created = TripPlan.objects.update_or_create(
            company_id=ctx["company"],
            project_id=ctx["project"],
            display_code=HOUSEHOLD_PLAN_DISPLAY_CODE,
            defaults={
                "district_id": ctx["district"],
                "city_id": ctx["city"],
                "zone_id": ctx["zone"],
                "staff_template_id": ctx["template"],
                "vehicle_id": ctx["vehicle"],
                "supervisor_id": ctx["supervisor"],
                "property_id": ctx["residential_property"],
                "sub_property_id": ctx["residential_sub_property"],
                "waste_type_id": ctx["wet_type"],
                "waste_type_ids": [ctx["wet_type"].unique_id],
                "collection_type": TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                "trip_trigger_weight_kg": 400,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": "08:00",
                "status": TripPlan.Status.ACTIVE,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "is_auto_assign": True,
                "repeat_days": [],
                "is_active": True,
                "is_deleted": False,
            },
        )
        plan.wards.set([ctx["ward"]])
        self.log(
            f"TripPlan {'created' if created else 'updated'}: {plan.unique_id} "
            f"[{HOUSEHOLD_PLAN_DISPLAY_CODE}] supervisor={ctx['supervisor'].username}"
        )
        return plan

    # ------------------------------------------------------------------
    def _seed_stops(self, ctx, plan):
        """Wipe and rebuild this plan's stops — mirrors
        driver_wet_dry_bin_trips.py's `_replace_stops`, so a re-run always
        leaves exactly these customers, in this sequence order.
        """
        TripPlanCollectionPoint.objects.filter(trip_plan_id=plan).delete()

        stops = []
        for sequence, customer in enumerate(ctx["customers"], start=1):
            stop = TripPlanCollectionPoint.objects.create(
                trip_plan_id=plan,
                customer_id=customer,
                company_id=ctx["company"],
                project_id=ctx["project"],
                collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                sequence=sequence,
                zone_id=ctx["zone"],
                ward_id=ctx["ward"],
                is_active=True,
                is_deleted=False,
            )
            stops.append(stop)
        self.log(f"Stops on {plan.display_code}: {len(stops)} (rebuilt from scratch).")
        self._prune_stale_daily_stops(plan, ctx["customers"])
        return stops

    # ------------------------------------------------------------------
    def _prune_stale_daily_stops(self, plan, customers):
        """Mirrors driver_wet_dry_bin_trips.py's `_prune_stale_daily_stops`
        for the household case — removes any never-collected household stop
        on this plan's assignments for a customer no longer on the plan.
        Collected stops are left alone (real audit history).
        """
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        deleted, _ = DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id__trip_plan_id=plan,
            is_collected=False,
        ).exclude(customer_id__in=customers).delete()
        if deleted:
            self.log(f"Pruned {deleted} stale (never-collected) daily stop(s) on {plan.display_code}.")

    # ------------------------------------------------------------------
    def _report(self, plan):
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        today = timezone.localdate()
        assignment = DailyTripAssignment.objects.filter(
            trip_plan_id=plan, trip_date=today, is_deleted=False
        ).order_by("created_at").first()
        if not assignment:
            self.log(f"  !! no assignment generated for {plan.unique_id}")
            return
        stops = DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=assignment, is_deleted=False
        )
        pending = stops.filter(status=DailyTripHouseholdCollection.STATUS_PENDING).count()
        self.log(
            f"  {assignment.unique_id} [{plan.display_code}] "
            f"stops={stops.count()} pending/collectible={pending}"
        )
