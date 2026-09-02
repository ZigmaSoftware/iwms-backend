"""20 household-collection TripPlans (and their customers) for
Blue Planet / Greater Noida BP.

TRIP PLANS ONLY — this seeder deliberately stops at the schedule-setup layer:
it creates TripPlan + TripPlanCollectionPoint + CustomerCreation rows and
NOTHING in daily-operations. No DailyTripAssignment, no
DailyTripHouseholdCollection, no WasteCollection. That is why every plan is
created with `is_auto_assign=False`: an auto-assign plan is picked up by
`generate_daily_trips.run_for_date()` (which DriverWetDryBinTripsSeeder calls
with force=True later in the same `seed all` run) and would immediately
produce the daily trip rows this seeder is meant not to create. Flip that flag
per plan from the UI when a plan should start generating daily trips.

Greater Noida BP is household-collection only (see BluePlanetSeeder), so each
stop is a real customer at a real Greater Noida locality with its own lat/lon
— never a standalone Collection_point, which belongs to bin collection.

Layout: 20 plans x 5 stops = 100 customers, dealt round-robin across the
project's three real wards (GNO Ward 1/2/3). Customer pins are scattered
deterministically around each ward's real boundary centroid
(WARD_REAL_BOUNDARIES in blue_planet.py), so they land inside their own ward
geofence on the map instead of drifting into a neighbouring one.

Depends on BluePlanetSeeder having run (company, project, wards, staff,
vehicles, property/waste-type masters). Skips with a log line rather than
raising if anything is missing, so `seed all` ordering can't hard-fail here.

Idempotent: every write is update_or_create keyed on a stable natural key
(plan display_code GNO-TP-01..20, customer id_no AADHAAR-BP-GNO-TP-xx-yy), so
re-running updates in place instead of duplicating.
"""

import math

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.customers.customercreation import CustomerCreation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
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
PROJECT_NAME = "Blue Planet Integrated Waste Management"
DEFAULT_CUSTOMER_PASSWORD = "Customer1"

PLAN_COUNT = 20
STOPS_PER_PLAN = 5

# Centroids of the real GNO ward boundary polygons defined in blue_planet.py
# (WARD_REAL_BOUNDARIES). Customers are scattered around these so each pin
# falls inside the ward geofence it is assigned to.
WARD_CENTERS = {
    "GNO Ward 1": (28.4670, 77.5190),   # Alpha 1 / Alpha 2 sector block
    "GNO Ward 2": (28.4750, 77.4955),   # Knowledge Park III block
    "GNO Ward 3": (28.4867, 77.5150),   # Pari Chowk / Surajpur block
}

# Real Greater Noida localities, grouped by the ward whose polygon contains
# them, with the pincode actually used for that locality.
WARD_LOCALITIES = {
    "GNO Ward 1": [
        ("Alpha 1 Market Road", "Alpha 1", "201308"),
        ("Alpha 2 Sector Road", "Alpha 2", "201308"),
        ("Beta 2 Sector Road", "Beta 2", "201309"),
        ("Gamma 1 Circle Road", "Gamma 1", "201310"),
    ],
    "GNO Ward 2": [
        ("Knowledge Park III Road", "Knowledge Park 3", "201313"),
        ("Knowledge Park II Road", "Knowledge Park 2", "201312"),
        ("Delta 1 Avenue", "Delta 1", "201311"),
        ("Sector 12 Main Road", "Sector 12", "201312"),
    ],
    "GNO Ward 3": [
        ("Pari Chowk Road", "Pari Chowk", "201310"),
        ("Surajpur Site Road", "Surajpur", "201306"),
        ("Kasna Village Road", "Kasna", "201310"),
        ("Tugalpur Main Road", "Tugalpur", "201306"),
    ],
}

# First/last name pools — combined deterministically so the 100 customers read
# as real North-Indian household names instead of "Customer 47".
FIRST_NAMES = [
    "Rakesh", "Sanjay", "Meera", "Vikram", "Poonam", "Amit", "Priyanka",
    "Rohit", "Neha", "Ankit", "Kavita", "Manoj", "Sunita", "Deepak",
    "Anjali", "Rajesh", "Shalini", "Gaurav", "Ritu", "Naveen",
]
LAST_NAMES = [
    "Gupta", "Malhotra", "Agarwal", "Chaudhary", "Bhatt", "Sharma", "Verma",
    "Singh", "Tyagi", "Chauhan", "Yadav", "Rawat", "Nagar", "Bansal",
    "Saxena", "Goel", "Mishra", "Pandey", "Sethi", "Khanna",
]

# Staggered start times so 20 plans don't all claim the same slot — the scan
# resolver picks "the active trip" by scheduled time, and identical times on
# one driver silently misroute scans between plans.
BASE_HOUR = 6


def _scatter(base_lat, base_lon, index, spread=0.004):
    """Deterministic golden-angle offset around an anchor point — same
    technique as blue_planet._scatter, kept local so this seeder does not
    import from the superadmin seeder. `spread` is deliberately tighter than
    the ward polygons (~0.008-0.012 across) so pins stay inside the geofence.
    """
    angle = (index * 137.508) % 360
    radius = spread * (0.35 + 0.65 * ((index * 0.618) % 1))
    return (
        base_lat + radius * math.cos(math.radians(angle)),
        base_lon + radius * math.sin(math.radians(angle)),
    )


class TripPlanGNOSeeder(BaseSeeder):
    name = "trip_plan_gno"

    # Overriding run() would otherwise drop BaseSeeder.run's @transaction.atomic,
    # leaving a mid-way failure with some of the 20 plans written and the rest
    # not. Every write here is idempotent, so a rollback + re-run is clean.
    @transaction.atomic
    def run(self):
        ctx = self._resolve_context()
        if ctx is None:
            return

        plans_created = plans_updated = 0
        customers_total = 0

        for plan_idx in range(1, PLAN_COUNT + 1):
            ward = ctx["wards"][(plan_idx - 1) % len(ctx["wards"])]
            customers = self._create_customers(ctx, ward, plan_idx)
            customers_total += len(customers)

            plan, created = self._create_trip_plan(ctx, ward, plan_idx)
            self._replace_stops(ctx, plan, customers)

            plans_created += int(created)
            plans_updated += int(not created)

        self.log(
            f"---Greater Noida BP trip plans ready: {plans_created} created, "
            f"{plans_updated} updated, {customers_total} customers across "
            f"{len(ctx['wards'])} wards (trip plans only — no daily trips)---"
        )

    # ------------------------------------------------------------------
    def _resolve_context(self):
        """Everything this seeder builds on top of, or None (with a log line)
        when BluePlanetSeeder hasn't run yet."""
        company = Company.objects.filter(name=COMPANY_NAME, is_deleted=False).first()
        if not company:
            self.log(f"Company '{COMPANY_NAME}' not found — run the superadmin seeders first.")
            return None

        project = Project.objects.filter(
            name=PROJECT_NAME, company_id=company, is_deleted=False
        ).first()
        if not project:
            self.log(f"Project '{PROJECT_NAME}' not found under {COMPANY_NAME} — skipping.")
            return None

        wards = [
            ward
            for ward in (
                Ward.objects.filter(
                    ward_name=name, company_id=company, project_id=project, is_deleted=False
                ).first()
                for name in WARD_CENTERS
            )
            if ward is not None
        ]
        if not wards:
            self.log("No GNO wards found — run BluePlanetSeeder first. Skipping.")
            return None

        district = District.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).first()
        city = City.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).first()
        property_obj = Property.objects.filter(
            company_id=company, project_id=project, property_name="Residential", is_deleted=False
        ).first()
        sub_property = SubProperty.objects.filter(
            property_id=property_obj, is_deleted=False
        ).first() if property_obj else None
        waste_types = list(
            WasteType.objects.filter(company_id=company, project_id=project, is_deleted=False)
        )
        vehicles = list(
            VehicleCreation.objects.filter(project_id=project, is_deleted=False).order_by("vehicle_no")
        )
        supervisor = Staffcreation.objects.filter(
            username="bp_gno_supervisor", is_deleted=False
        ).first()

        missing = [
            label
            for label, value in (
                ("district", district), ("city", city), ("property", property_obj),
                ("sub_property", sub_property), ("waste_types", waste_types),
                ("vehicles", vehicles), ("supervisor", supervisor),
                # Non-nullable on CustomerCreation — bail out rather than
                # blowing up mid-loop on an IntegrityError.
                ("state", district.state_id_id if district else None),
                ("country", district.country_id_id if district else None),
            )
            if not value
        ]
        if missing:
            self.log(f"Skipping — BluePlanetSeeder prerequisites missing: {', '.join(missing)}.")
            return None

        staff_templates = self._staff_templates(company, project)
        if not staff_templates:
            self.log("No GNO driver/operator staff found — run BluePlanetSeeder first. Skipping.")
            return None

        return {
            "company": company,
            "project": project,
            "district": district,
            "city": city,
            # CustomerCreation.state/.country are both non-nullable, and
            # District carries its own FK to each — take them from there
            # rather than walking state -> country.
            "state": district.state_id,
            "country": district.country_id,
            "wards": wards,
            "property": property_obj,
            "sub_property": sub_property,
            "waste_types": waste_types,
            "vehicles": vehicles,
            "supervisor": supervisor,
            "staff_templates": staff_templates,
        }

    def _staff_templates(self, company, project):
        """Pair the project's seeded drivers with its operators so 20 plans
        spread over several crews instead of piling onto one driver."""
        drivers = list(
            Staffcreation.objects.filter(
                username__startswith="bp_gno_driver", is_deleted=False
            ).order_by("username")
        )
        operators = list(
            Staffcreation.objects.filter(
                username__startswith="bp_gno_operator", is_deleted=False
            ).order_by("username")
        )
        if not drivers or not operators:
            return []

        templates = []
        for driver in drivers:
            for operator in operators:
                template, _ = StaffTemplate.objects.update_or_create(
                    driver_id=driver,
                    operator_id=operator,
                    defaults={
                        "company_id": company,
                        "project_id": project,
                        "extra_operator_id": [],
                        "status": StaffTemplate.Status.ACTIVE,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                templates.append(template)
        return templates

    # ------------------------------------------------------------------
    def _create_customers(self, ctx, ward, plan_idx):
        """The STOPS_PER_PLAN households this plan collects from. Keyed on a
        stable id_no so a re-run updates the same rows."""
        center_lat, center_lon = WARD_CENTERS[ward.ward_name]
        localities = WARD_LOCALITIES[ward.ward_name]

        customers = []
        for stop_idx in range(1, STOPS_PER_PLAN + 1):
            # Globally unique, stable ordinal for this (plan, stop) pair —
            # drives the name, the pin offset and every natural key below.
            ordinal = (plan_idx - 1) * STOPS_PER_PLAN + stop_idx
            street, area, pincode = localities[(ordinal - 1) % len(localities)]
            name = (
                f"{FIRST_NAMES[(ordinal - 1) % len(FIRST_NAMES)]} "
                f"{LAST_NAMES[(ordinal // 3) % len(LAST_NAMES)]}"
            )
            lat, lon = _scatter(center_lat, center_lon, ordinal)
            id_no = f"AADHAAR-BP-GNO-TP-{plan_idx:02d}-{stop_idx:02d}"

            customer, _ = CustomerCreation.objects.update_or_create(
                company_id=ctx["company"],
                project_id=ctx["project"],
                id_no=id_no,
                defaults={
                    "customer_name": name,
                    "contact_no": f"9611{ordinal:06d}",
                    "username": f"bp_gno_tp{plan_idx:02d}_customer{stop_idx:02d}",
                    "password": make_password(DEFAULT_CUSTOMER_PASSWORD),
                    "password_crt_date": timezone.now(),
                    "building_no": f"{(ordinal % 90) + 1}",
                    "street": street,
                    "area": area,
                    "ward": ward,
                    "zone": ward.zone_id,
                    "city": ctx["city"],
                    "district": ctx["district"],
                    "state": ctx["state"],
                    "country": ctx["country"],
                    "panchayat_id": None,
                    "pincode": pincode,
                    "latitude": f"{lat:.6f}",
                    "longitude": f"{lon:.6f}",
                    "sqft": "1200.00",
                    "water_consumption_lpd": "240.00",
                    "waste_collection_kg_per_day": "3.50",
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "member_count": 4,
                    "family_members": [
                        {
                            "member_name": f"{name} Family {member_idx}",
                            "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                            "id_no": f"{id_no}-FM{member_idx}",
                        }
                        for member_idx in range(1, 5)
                    ],
                    "property_ref": ctx["property"],
                    "sub_property": ctx["sub_property"],
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            customer.waste_types.set(ctx["waste_types"])
            customers.append(customer)
        return customers

    def _create_trip_plan(self, ctx, ward, plan_idx):
        """One household plan, keyed on its stable display_code.

        display_code is passed explicitly rather than left to TripPlan.save()'s
        auto-generator: that generator appends an incrementing sequence, so
        letting it run would mint a new code on every re-seed instead of
        matching the existing row.
        """
        template = ctx["staff_templates"][(plan_idx - 1) % len(ctx["staff_templates"])]
        vehicle = ctx["vehicles"][(plan_idx - 1) % len(ctx["vehicles"])]
        waste_type = ctx["waste_types"][(plan_idx - 1) % len(ctx["waste_types"])]
        scheduled = f"{BASE_HOUR + ((plan_idx - 1) // 4):02d}:{((plan_idx - 1) % 4) * 15:02d}"

        plan, created = TripPlan.objects.update_or_create(
            display_code=f"GNO-TP-{plan_idx:02d}",
            defaults={
                "company_id": ctx["company"],
                "project_id": ctx["project"],
                "district_id": ctx["district"],
                "city_id": ctx["city"],
                "zone_id": ward.zone_id,
                "panchayat_id": None,
                "staff_template_id": template,
                "vehicle_id": vehicle,
                "supervisor_id": ctx["supervisor"],
                "property_id": ctx["property"],
                "sub_property_id": ctx["sub_property"],
                "waste_type_id": waste_type,
                "waste_type_ids": [waste_type.unique_id],
                "collection_type": TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                "trip_trigger_weight_kg": 400,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": scheduled,
                # See the module docstring: trip plans only, so these must not
                # be swept up by generate_daily_trips.run_for_date().
                "is_auto_assign": False,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "status": TripPlan.Status.ACTIVE,
                "is_active": True,
                "is_deleted": False,
            },
        )
        plan.wards.set([ward])
        return plan, created

    def _replace_stops(self, ctx, plan, customers):
        """Retire whatever stops the plan already had, then lay down the
        current set. Sequences on the retired rows are pushed past the new
        ones first: `sequence` is unique per plan, so reusing 1..N while the
        old rows still hold them would collide."""
        existing = TripPlanCollectionPoint.objects.filter(trip_plan_id=plan)
        if existing.exists():
            max_sequence = existing.aggregate(max_sequence=Max("sequence"))["max_sequence"] or 0
            existing.update(
                sequence=F("sequence") + max_sequence + len(customers) + 1000,
                is_deleted=True,
                is_active=False,
            )

        for idx, customer in enumerate(customers, start=1):
            TripPlanCollectionPoint.objects.update_or_create(
                trip_plan_id=plan,
                customer_id=customer,
                defaults={
                    "company_id": ctx["company"],
                    "project_id": ctx["project"],
                    "collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                    "sequence": idx,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
