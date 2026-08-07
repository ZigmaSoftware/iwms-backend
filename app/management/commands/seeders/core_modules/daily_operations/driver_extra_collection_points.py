"""10 more collectable bin-collection points for `driver_user`.

Adds 10 brand-new `Collection_point` rows (each with its own bin) under
Blue Planet / Palakkad BP, and appends them as additional stops on
`driver_user`'s existing bin-collection TripPlan
(`DRIVERUSER-PAL-BIN-01`, seeded by `driver_palakkad_trips.py`) — so the
driver has a realistic-sized bin round instead of just the original one
collection point's 3 bins.

Requires `driver-trips` (or `all`) to have already run — needs the
company/project/district/city/zone/ward masters, the waste types, and the
bin TripPlan it appends to.

Idempotent — `update_or_create` on cp_name / display_code+sequence.
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.assets.bins import BinType, Bins
from app.models.schedule_masters.collection_point import Collection_point
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
BIN_PLAN_DISPLAY_CODE = "DRIVERUSER-PAL-BIN-01"

# 10 new collection points, each with one bin — coordinates walk further
# down the same roads as the original PAL_CUSTOMERS list so they read as
# a plausible extension of the same round.
EXTRA_POINTS = [
    ("CP-PAL-02", "10.7923", "76.6604"),
    ("CP-PAL-03", "10.7927", "76.6608"),
    ("CP-PAL-04", "10.7931", "76.6612"),
    ("CP-PAL-05", "10.7935", "76.6616"),
    ("CP-PAL-06", "10.7939", "76.6620"),
    ("CP-PAL-07", "10.7943", "76.6624"),
    ("CP-PAL-08", "10.7947", "76.6628"),
    ("CP-PAL-09", "10.7951", "76.6632"),
    ("CP-PAL-10", "10.7955", "76.6636"),
    ("CP-PAL-11", "10.7959", "76.6640"),
]


class DriverExtraCollectionPointsSeeder(BaseSeeder):
    name = "driver_extra_collection_points"

    def run(self):
        ctx = self._resolve_context()
        if ctx is None:
            return

        points = self._seed_collection_points(ctx)
        bins = self._seed_bins(ctx, points)
        added = self._append_stops(ctx, bins)

        self.log(
            f"---{len(points)} extra collection points / {len(bins)} bins ready, "
            f"{added} new stops appended to {BIN_PLAN_DISPLAY_CODE}---"
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
        waste_type = WasteType.objects.filter(**scope).order_by("waste_type_name").first()

        missing = [
            label for label, value in (
                ("district", district), ("city", city), ("zone", zone),
                ("ward", ward), ("waste type", waste_type),
            ) if not value
        ]
        if missing:
            self.log(f"Missing {PROJECT_NAME} masters: {', '.join(missing)}. Seed masters first.")
            return None

        driver = Staffcreation.objects.filter(username=DRIVER_USERNAME, is_deleted=False).first()
        if not driver:
            self.log(f"'{DRIVER_USERNAME}' not found — run the user-creations seeders first.")
            return None

        bin_plan = TripPlan.objects.filter(
            company_id=company, project_id=project,
            display_code=BIN_PLAN_DISPLAY_CODE, is_deleted=False,
        ).first()
        if not bin_plan:
            self.log(
                f"TripPlan '{BIN_PLAN_DISPLAY_CODE}' not found — run the "
                f"'driver-trips' seed group first."
            )
            return None

        return {
            "company": company, "project": project,
            "district": district, "city": city, "zone": zone, "ward": ward,
            "waste_type": waste_type, "driver": driver, "bin_plan": bin_plan,
        }

    # ------------------------------------------------------------------
    def _seed_collection_points(self, ctx):
        points = []
        created = 0
        for cp_name, lat, lng in EXTRA_POINTS:
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
    def _seed_bins(self, ctx, points):
        bins = []
        created = 0
        for cp in points:
            bin_name = f"{cp.cp_name} {ctx['waste_type'].waste_type_name}"
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
                    "wastetype_id": ctx["waste_type"],
                    "bin_capacity": 240,
                    "bin_type": BinType.MEDIUM,
                    "bin_image": "",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            bins.append(bin_obj)
            created += int(was_created)
        self.log(f"Bins ready: {len(bins)} ({created} created).")
        return bins

    # ------------------------------------------------------------------
    def _append_stops(self, ctx, bins):
        plan = ctx["bin_plan"]
        next_sequence = (
            TripPlanCollectionPoint.objects.filter(trip_plan_id=plan, is_deleted=False)
            .order_by("-sequence")
            .values_list("sequence", flat=True)
            .first() or 0
        ) + 1

        added = 0
        for offset, bin_obj in enumerate(bins):
            _, created = TripPlanCollectionPoint.objects.update_or_create(
                trip_plan_id=plan,
                collection_point_id=bin_obj.collection_point_id,
                bin_id=bin_obj,
                defaults={
                    "company_id": ctx["company"],
                    "project_id": ctx["project"],
                    "collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                    "sequence": next_sequence + offset,
                    "zone_id": ctx["zone"],
                    "ward_id": ctx["ward"],
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            added += int(created)

        # New stops only apply to trips generated from now on — regenerate
        # today's assignment so the driver sees them immediately.
        from app.management.commands.generate_daily_trips import run_for_date
        today = timezone.localdate()
        result = run_for_date(today, force=True)
        self.log(f"Regenerated assignments for {today}: {result}")

        return added
