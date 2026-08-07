"""Daily trip assignments for `driver_user` under Blue Planet / Palakkad BP.

Builds the whole chain the app needs, in the order the flow requires:

    Customers (household targets)
        └─ StaffTemplate (driver_user + operator_user)
             └─ TripPlan  x2   (bin_collection + household_collection)
                  └─ TripPlanCollectionPoint   (bin stops / household stops)
                       └─ run_for_date(force=True)
                            └─ DailyTripAssignment
                                 ├─ DailyTripCollectionPoint     (bin)
                                 └─ DailyTripHouseholdCollection (household)

Why this exists: the stock seeders build trip plans under the **IWMS**
company while `driver_user`/`supervisor_user` and every CustomerCreation row
live under **Blue Planet**. `CompanyScopedViewSet` filters by the caller's
company, so those trips are invisible in the app, and household stops can
never resolve (no customers in that company). Everything here is created
under Blue Planet / Palakkad BP so both the driver and supervisor apps see
real data.

`collection_type` on the TripPlan is what decides bin vs household — a single
plan only ever produces one kind (see
`app/signals/trip_plan_signals.py::sync_daily_assignment_stops_from_plan`),
hence two plans.

Idempotent: get_or_create / update_or_create throughout, safe to re-run.
"""

from datetime import time

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.assets.bins import Bins
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.role_assigns.userType import UserType
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Palakkad BP"

DRIVER_USERNAME = "driver_user"
OPERATOR_USERNAME = "operator_user"
SUPERVISOR_USERNAME = "supervisor_user"

DEFAULT_CUSTOMER_PASSWORD = "Customer1"

# 12 household + 2 bulk-waste generators, so both household_collection and
# bulk_waste_collection stop types have something to resolve.
PAL_CUSTOMERS = [
    ("PAL Ramesh",   "9001000001", "1A",  "Palakkad Main Road", "PAL Area 1", "678001", "10.7867", "76.6548", False),
    ("PAL Lakshmi",  "9001000002", "2B",  "Fort Road",          "PAL Area 1", "678001", "10.7871", "76.6552", False),
    ("PAL Anand",    "9001000003", "3C",  "Kalpathy Street",    "PAL Area 2", "678002", "10.7875", "76.6556", False),
    ("PAL Geetha",   "9001000004", "4D",  "Chandranagar Road",  "PAL Area 2", "678002", "10.7879", "76.6560", False),
    ("PAL Mohan",    "PAL9001005", "5E",  "Stadium Road",       "PAL Area 3", "678003", "10.7883", "76.6564", False),
    ("PAL Sujatha",  "9001000006", "6F",  "Head Post Road",     "PAL Area 3", "678003", "10.7887", "76.6568", False),
    ("PAL Vinod",    "9001000007", "7G",  "Coimbatore Road",    "PAL Area 4", "678004", "10.7891", "76.6572", False),
    ("PAL Asha",     "9001000008", "8H",  "Mele Pattambi Road", "PAL Area 4", "678004", "10.7895", "76.6576", False),
    ("PAL Rajan",    "9001000009", "9I",  "Olavakkode Road",    "PAL Area 5", "678005", "10.7899", "76.6580", False),
    ("PAL Bindu",    "9001000010", "10J", "Yakkara Road",       "PAL Area 5", "678005", "10.7903", "76.6584", False),
    ("PAL Suresh",   "9001000011", "11K", "Kunnathurmedu Road", "PAL Area 6", "678006", "10.7907", "76.6588", False),
    ("PAL Nisha",    "9001000012", "12L", "Puthur Road",        "PAL Area 6", "678006", "10.7911", "76.6592", False),
    # Bulk waste generators (hotels / institutions)
    ("PAL Grand Hotel",  "9001000013", "13M", "Town Bus Stand Road", "PAL Area 7", "678007", "10.7915", "76.6596", True),
    ("PAL City College",  "9001000014", "14N", "College Road",        "PAL Area 7", "678007", "10.7919", "76.6600", True),
]


class DriverPalakkadTripsSeeder(BaseSeeder):
    """`driver_user` is bin-collection only — the app has no household/bulk
    collection UI, so this seeder no longer creates a household or bulk
    TripPlan for them at all (previously it did, then a separate
    `driver-bin-only` seed group deactivated them after the fact — that
    left a re-run of this seeder resurrecting them every time). Any
    household/bulk plan or assignment from an older run of this seeder is
    cleaned up on every run, so re-running it is enough to fully undo that
    old behaviour without needing the `driver-bin-only` group afterwards.
    """

    name = "driver_palakkad_trips"

    # ------------------------------------------------------------------
    def run(self):
        ctx = self._resolve_context()
        if ctx is None:
            return

        template = self._seed_staff_template(ctx)
        if template is None:
            return

        bin_plan = self._seed_trip_plan(
            ctx, template, TripPlan.COLLECTION_TYPE_BIN, "DRIVERUSER-PAL-BIN-01",
            time(7, 0),
        )
        if bin_plan is None:
            return

        self._seed_bin_stops(ctx, bin_plan)
        self._retire_household_and_bulk(ctx, template)

        self._generate_assignments()
        self._report(ctx, [bin_plan])

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
        collection_point = Collection_point.objects.filter(**scope).first()
        bins = list(Bins.objects.filter(**scope).order_by("unique_id"))
        waste_types = list(WasteType.objects.filter(**scope).order_by("waste_type_name"))
        property_ref = Property.objects.filter(**scope).first()
        sub_property = SubProperty.objects.filter(**scope).first()

        missing = [
            label
            for label, value in (
                ("district", district), ("city", city), ("zone", zone), ("ward", ward),
                ("vehicle", vehicle), ("collection point", collection_point),
                ("bins", bins), ("waste types", waste_types),
                ("property", property_ref), ("sub property", sub_property),
            )
            if not value
        ]
        if missing:
            self.log(f"Missing {PROJECT_NAME} masters: {', '.join(missing)}. Seed masters first.")
            return None

        driver = Staffcreation.objects.filter(username=DRIVER_USERNAME, is_deleted=False).first()
        operator = Staffcreation.objects.filter(username=OPERATOR_USERNAME, is_deleted=False).first()
        supervisor = Staffcreation.objects.filter(username=SUPERVISOR_USERNAME, is_deleted=False).first()
        if not driver:
            self.log(f"'{DRIVER_USERNAME}' not found — run the user-creations seeders first.")
            return None
        if not operator:
            # StaffTemplate.operator_id is required; fall back to the driver so
            # the merged driver/captain flow still works.
            operator = driver

        # AuthUserSeeder creates driver_user/operator_user under WHATEVER
        # company/project happens to sort first in the DB (no name filter),
        # which is almost never Blue Planet/Palakkad BP. Everything this
        # seeder builds — the trip plan, its stops, the supervisor's own
        # tenancy — lives under Blue Planet/Palakkad BP, so pin the driver's
        # (and operator's) own Staffcreation row there too. Without this,
        # CompanyScopedViewSet silently filters every trip out of the
        # supervisor app: the trip plan is in the right project, but
        # `supervisor_user.project_id` (copied from `driver.project_id` by
        # SupervisorUserSeeder) would still point at the stale one, and the
        # supervisor's queryset never matches it.
        for staff in {driver, operator}:
            if staff.company_id_id != company.unique_id or staff.project_id_id != project.unique_id:
                staff.company_id = company
                staff.project_id = project
                staff.district_id = district
                staff.city_id = city
                staff.zone_id = zone
                staff.ward_id = ward
                staff.save(update_fields=[
                    "company_id", "project_id", "district_id", "city_id",
                    "zone_id", "ward_id", "updated_at",
                ])

        if not supervisor:
            self.log(f"'{SUPERVISOR_USERNAME}' not found — run the supervisor-user seeder first.")
            return None

        return {
            "company": company, "project": project,
            "district": district, "city": city, "zone": zone, "ward": ward,
            "state": getattr(district, "state_id", None),
            "country": Country.objects.filter(name="India").first(),
            "vehicle": vehicle, "collection_point": collection_point,
            "bins": bins, "waste_types": waste_types,
            "property_ref": property_ref, "sub_property": sub_property,
            "driver": driver, "operator": operator, "supervisor": supervisor,
        }

    # ------------------------------------------------------------------
    def _seed_customers(self, ctx):
        customer_type = UserType.objects.filter(name__iexact="customer").first()
        if not customer_type:
            self.log("UserType 'customer' missing — seed role-assigns first.")
            return []

        now = timezone.now()
        created = 0
        customers = []
        for (name, contact, building, street, area, pincode,
             lat, lng, is_bulk) in PAL_CUSTOMERS:
            id_no = f"AADHAAR-PAL-{contact[-4:]}"
            customer, was_created = CustomerCreation.objects.update_or_create(
                company_id=ctx["company"],
                project_id=ctx["project"],
                id_no=id_no,
                defaults={
                    "customer_name": name,
                    "contact_no": contact,
                    "username": contact,
                    "password": make_password(DEFAULT_CUSTOMER_PASSWORD),
                    "password_crt_date": now,
                    "building_no": building,
                    "street": street,
                    "area": area,
                    "ward": ctx["ward"],
                    "zone": ctx["zone"],
                    "city": ctx["city"],
                    "district": ctx["district"],
                    "state": ctx["state"],
                    "country": ctx["country"],
                    "pincode": pincode,
                    "latitude": lat,
                    "longitude": lng,
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "property_ref": ctx["property_ref"],
                    "sub_property": ctx["sub_property"],
                    "user_type_id": customer_type,
                    "is_bulkwaste_generator": is_bulk,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            customer.waste_types.set(ctx["waste_types"])
            customers.append(customer)
            created += int(was_created)

        self.log(
            f"Customers ready: {len(customers)} "
            f"({created} created) in {PROJECT_NAME} — "
            f"{sum(1 for c in customers if not c.is_bulkwaste_generator)} household, "
            f"{sum(1 for c in customers if c.is_bulkwaste_generator)} bulk."
        )
        return customers

    # ------------------------------------------------------------------
    def _seed_staff_template(self, ctx):
        template, created = StaffTemplate.objects.get_or_create(
            company_id=ctx["company"],
            project_id=ctx["project"],
            driver_id=ctx["driver"],
            operator_id=ctx["operator"],
            is_deleted=False,
            defaults={"is_active": True},
        )
        self.log(
            f"StaffTemplate {'created' if created else 'exists'}: "
            f"{template.unique_id} (driver={ctx['driver'].username}, "
            f"operator={ctx['operator'].username})"
        )
        return template

    # ------------------------------------------------------------------
    def _seed_trip_plan(self, ctx, template, collection_type, display_code, scheduled_time):
        plan, created = TripPlan.objects.update_or_create(
            company_id=ctx["company"],
            project_id=ctx["project"],
            display_code=display_code,
            defaults={
                "district_id": ctx["district"],
                "city_id": ctx["city"],
                "zone_id": ctx["zone"],
                "staff_template_id": template,
                "vehicle_id": ctx["vehicle"],
                "supervisor_id": ctx["supervisor"],
                "waste_type_id": ctx["waste_types"][0],
                "property_id": ctx["property_ref"],
                "sub_property_id": ctx["sub_property"],
                "collection_type": collection_type,
                "trip_trigger_weight_kg": 800,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": scheduled_time,
                "status": TripPlan.Status.ACTIVE,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "is_auto_assign": True,
                # Empty repeat_days means "no scheduled weekday", so generation
                # must be forced — which is exactly what _generate_assignments
                # does (mirrors the stock DailyTripAssignmentSeeder).
                "repeat_days": [],
                "is_active": True,
                "is_deleted": False,
            },
        )
        plan.wards.set([ctx["ward"]])
        plan.waste_types.set(ctx["waste_types"])
        self.log(
            f"TripPlan {'created' if created else 'updated'}: {plan.unique_id} "
            f"[{collection_type}] supervisor={ctx['supervisor'].username}"
        )
        return plan

    # ------------------------------------------------------------------
    def _seed_bin_stops(self, ctx, plan):
        count = 0
        for sequence, bin_obj in enumerate(ctx["bins"], start=1):
            _, created = TripPlanCollectionPoint.objects.update_or_create(
                trip_plan_id=plan,
                sequence=sequence,
                defaults={
                    "company_id": ctx["company"],
                    "project_id": ctx["project"],
                    "collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                    "collection_point_id": ctx["collection_point"],
                    "bin_id": bin_obj,
                    "zone_id": ctx["zone"],
                    "ward_id": ctx["ward"],
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            count += int(created)
        self.log(f"Bin stops on {plan.unique_id}: {len(ctx['bins'])} ({count} created)")

    # ------------------------------------------------------------------
    def _seed_geo_household_stop(self, ctx, plan, collection_type):
        """A single geo-scoped stop, not one row per customer.

        `_customers_for_household_stop` expands a ward/zone-scoped stop into
        every matching CustomerCreation, picking bulk vs normal households
        from the stop's `collection_type` (`is_bulkwaste_generator` match).
        """
        TripPlanCollectionPoint.objects.update_or_create(
            trip_plan_id=plan,
            sequence=1,
            defaults={
                "company_id": ctx["company"],
                "project_id": ctx["project"],
                "collection_type": collection_type,
                "zone_id": ctx["zone"],
                "ward_id": ctx["ward"],
                "is_active": True,
                "is_deleted": False,
            },
        )
        self.log(
            f"Geo stop on {plan.unique_id} [{collection_type}] — "
            f"expanded per customer by the trip-plan signal."
        )

    # ------------------------------------------------------------------
    def _retire_household_and_bulk(self, ctx, template):
        """Completely remove any household/bulk TripPlan this seeder created
        in an older run, and every DailyTripAssignment generated from one —
        hard-deleted, not soft-cancelled. driver_user has no household/bulk
        collection UI at all, so these shouldn't exist in any form,
        including a lingering "Cancelled" row.

        `DailyTripAssignment`'s child tables (DailyTripHouseholdCollection,
        DailyTripCollectionPoint) CASCADE off it, and nothing else holds a
        PROTECT reference to a household/bulk assignment (unlike bin
        assignments, which BinCollectionEvent/DailyTripLog protect) — a
        household stop is never bin-scanned, so hard delete is safe here.

        This makes re-running the seeder itself enough to undo the old
        household/bulk plans — no separate cleanup step needed afterwards.
        """
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment

        plans = TripPlan.objects.filter(
            company_id=ctx["company"],
            project_id=ctx["project"],
            staff_template_id=template,
            collection_type__in=[
                TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                TripPlan.COLLECTION_TYPE_BULK,
            ],
        )
        plan_count = plans.count()
        if not plan_count:
            return

        assignment_count = DailyTripAssignment.objects.filter(trip_plan_id__in=plans).count()
        DailyTripAssignment.objects.filter(trip_plan_id__in=plans).delete()

        plans.delete()

        self.log(
            f"Removed {plan_count} old household/bulk TripPlan(s) and "
            f"{assignment_count} DailyTripAssignment row(s) (with their "
            f"child stops) for {DRIVER_USERNAME} — completely, not cancelled."
        )

    # ------------------------------------------------------------------
    def _generate_assignments(self):
        from app.management.commands.generate_daily_trips import run_for_date

        today = timezone.localdate()
        # force=True because repeat_days is empty (same as the stock
        # DailyTripAssignmentSeeder). The post_save signal on the assignment
        # clones the plan's stops into the daily child tables.
        result = run_for_date(today, force=True)
        self.log(f"Generated assignments for {today}: {result}")

    # ------------------------------------------------------------------
    def _report(self, ctx, plans):
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        from app.models.schedule_masters.daily_trip_collection_point import (
            DailyTripCollectionPoint,
        )
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        today = timezone.localdate()
        for plan in plans:
            assignment = DailyTripAssignment.objects.filter(
                trip_plan_id=plan, trip_date=today, is_deleted=False
            ).first()
            if not assignment:
                self.log(f"  !! no assignment generated for {plan.unique_id}")
                continue
            bins = DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            ).count()
            households = DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            ).count()
            self.log(
                f"  {assignment.unique_id} [{plan.collection_type}] "
                f"bin_stops={bins} household_stops={households}"
            )

        self.log(
            f"---driver_user Palakkad trips seeded "
            f"({COMPANY_NAME} / {PROJECT_NAME})---"
        )
