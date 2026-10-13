"""Sample static routes for the Static Route Map — local/demo data only.

For every known project: one bin-collection and one household-collection
trip plan over real places in the project's city, each with a detour, its
static route saved (road path from OpenRouteService), and today's daily
trip part-way through — some stops collected, one in progress, the rest
pending — so the map and tracking pages show live-looking data.

Re-runnable: plans are keyed by display code (SR-<CITY>-BIN / SR-<CITY>-HH),
sample collection points / customers by name, and today's trip is only
created (and its progress simulated) once.

    python manage.py seed_static_route_samples
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.route_detour_waypoint import RouteDetourWaypoint
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.plant import Plant
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.waste_masters.bins import Bins
from app.models.superadmin_masters.project import Project
from app.services.static_route import PLANT_START_KEY, cp_key, save_plan_static_route

NAME_PREFIX = "SR"

# Real places per city, in visiting order. Coordinates are approximate
# (street level); OpenRouteService snaps them to the nearest road.
CITIES = {
    "Blue Planet Integrated Waste Management": {
        "code": "GNO",
        "plant": ("Greater Noida Waste Processing Site", 28.4436, 77.5248),
        "bins": [
            ("Knowledge Park II", 28.4589, 77.4953),
            ("Beta 1 Sector Gate", 28.4660, 77.5007),
            ("Pari Chowk", 28.4650, 77.5110),
            ("Alpha 1 Market", 28.4729, 77.5121),
            ("Gamma 1 Commercial Belt", 28.4807, 77.5098),
            ("Delta 1 Market", 28.4762, 77.5203),
        ],
        "households": [
            ("Gamma 1 · House 12", 28.4821, 77.5112),
            ("Gamma 1 · House 27", 28.4830, 77.5127),
            ("Gamma 1 · House 41", 28.4839, 77.5141),
            ("Gamma 2 · House 8", 28.4851, 77.5160),
            ("Gamma 2 · House 19", 28.4862, 77.5176),
            ("Alpha 2 · House 5", 28.4780, 77.5172),
            ("Alpha 2 · House 16", 28.4768, 77.5158),
            ("Alpha 2 · House 30", 28.4756, 77.5144),
        ],
    },
    "Palakkad BP": {
        "code": "PAL",
        "plant": None,  # the project's own plant
        "bins": [
            ("Kalmandapam Junction", 10.7662, 76.6748),
            ("Chandranagar Junction", 10.7585, 76.6670),
            ("Palakkad Fort Road", 10.7653, 76.6560),
            ("Sultanpet Junction", 10.7739, 76.6533),
            ("Stadium Bus Stand", 10.7766, 76.6545),
            ("Olavakkode Junction", 10.7960, 76.6478),
        ],
        "households": [
            ("Nurani · House 3", 10.7680, 76.6640),
            ("Nurani · House 11", 10.7688, 76.6652),
            ("Nurani · House 24", 10.7696, 76.6664),
            ("Kalmandapam · House 7", 10.7671, 76.6703),
            ("Kalmandapam · House 15", 10.7663, 76.6718),
            ("Kalmandapam · House 22", 10.7655, 76.6733),
            ("Chandranagar · House 9", 10.7601, 76.6688),
            ("Chandranagar · House 18", 10.7592, 76.6676),
        ],
    },
    "prj": {
        "code": "HYD",
        "plant": None,
        "bins": [
            ("Nampally Station Road", 17.3925, 78.4686),
            ("Abids Circle", 17.3916, 78.4762),
            ("Koti Bus Stop", 17.3852, 78.4867),
            ("Lakdikapul", 17.4037, 78.4631),
            ("Masab Tank", 17.4005, 78.4522),
            ("Mehdipatnam Rythu Bazar", 17.3946, 78.4405),
        ],
        "households": [
            ("Humayun Nagar · House 4", 17.3938, 78.4448),
            ("Humayun Nagar · House 13", 17.3947, 78.4461),
            ("Humayun Nagar · House 25", 17.3956, 78.4474),
            ("Vijay Nagar Colony · House 6", 17.3968, 78.4493),
            ("Vijay Nagar Colony · House 17", 17.3977, 78.4508),
            ("Vijay Nagar Colony · House 29", 17.3986, 78.4522),
            ("Mehdipatnam · House 2", 17.3961, 78.4420),
            ("Mehdipatnam · House 10", 17.3952, 78.4433),
        ],
    },
}

# Today's trip progress: this share of stops collected, the next one in
# progress, the rest pending.
COLLECTED_SHARE = 0.5
MINUTES_PER_STOP = 12


def _clone_kwargs(instance, skip=()):
    """Field values of `instance` usable to create a sibling row: every
    concrete column except the primary key, timestamps and `skip`."""
    skipped = {"created_at", "updated_at", *skip}
    return {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
        if not field.primary_key and field.name not in skipped and field.attname not in skipped
    }


def _coord(value):
    return Decimal(str(value)).quantize(Decimal("0.000001"))


class Command(BaseCommand):
    help = "Seed sample bin + household static routes (with today's live trips) for each project."

    def handle(self, *args, **options):
        for project in Project.objects.filter(is_deleted=False):
            city = CITIES.get(project.name)
            if not city:
                self.stdout.write(f"- {project.name}: no sample places defined, skipped.")
                continue
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{project.name} ({city['code']})"))
            try:
                self._seed_project(project, city)
            except _Skip as exc:
                self.stdout.write(self.style.WARNING(f"  skipped: {exc}"))

    # ------------------------------------------------------------------

    def _seed_project(self, project, city):
        scope = {"company_id": project.company_id, "project_id": project.unique_id}

        plant = self._plant(project, city, scope)
        cp_template = Collection_point.objects.filter(**scope, is_deleted=False).first()
        bin_template = Bins.objects.filter(**scope, is_deleted=False).first()
        customer_template = (
            CustomerCreation.objects.filter(**scope, is_deleted=False, is_bulkwaste_generator=False)
            .exclude(ward_id=None)
            .first()
        )
        if not (cp_template and bin_template and customer_template):
            raise _Skip("needs at least one collection point, bin and household customer to copy from")

        plan_defaults = self._plan_defaults(project, scope, cp_template, bin_template, customer_template)

        bin_plan = self._plan(f"{NAME_PREFIX}-{city['code']}-BIN", TripPlan.COLLECTION_TYPE_BIN, plan_defaults)
        points = [
            self._collection_point(scope, cp_template, bin_template, name, lat, lng)
            for name, lat, lng in city["bins"]
        ]
        self._replace_plan_stops(bin_plan, [
            {"collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
             "collection_point_id": cp.unique_id, "bin_id": bin_.unique_id}
            for cp, bin_ in points
        ])
        self._detour(bin_plan, after=points[1][0], before=points[2][0])

        hh_plan = self._plan(f"{NAME_PREFIX}-{city['code']}-HH", TripPlan.COLLECTION_TYPE_HOUSEHOLD, plan_defaults)
        customers = [
            self._customer(scope, customer_template, index, name, lat, lng)
            for index, (name, lat, lng) in enumerate(city["households"], start=1)
        ]
        self._replace_plan_stops(hh_plan, [
            {"collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
             "customer_id": customer.unique_id}
            for customer in customers
        ])
        self._detour(hh_plan, after=customers[2], before=customers[3], key=f"cust:{customers[2].unique_id}")

        for plan in (bin_plan, hh_plan):
            saved, routing_error, _ = save_plan_static_route(plan)
            km = saved.distance_meters / 1000
            note = f"  road path failed: {routing_error}" if routing_error else ""
            self.stdout.write(
                f"  {plan.display_code}: {len(saved.stops)} stops, {len(saved.detour_waypoints)} detour, "
                f"{km:.1f} km / {saved.duration_seconds / 60:.0f} min, saved v{saved.version}"
                + (f" (plant: {plant.name})" if plant else " (no plant)")
                + note
            )
            trip, created = self._todays_trip(plan)
            self.stdout.write(
                f"    today's trip {trip.unique_id}: "
                + (self._simulate_progress(trip, plan) if created else "already existed, left as is")
            )

    # ------------------------------------------------------------------
    # Masters
    # ------------------------------------------------------------------

    def _plant(self, project, city, scope):
        plant = Plant.objects.filter(project_id=project.unique_id, is_active=True, is_deleted=False).first()
        if plant or not city["plant"]:
            return plant
        name, lat, lng = city["plant"]
        return Plant.objects.create(**scope, name=name, latitude=_coord(lat), longitude=_coord(lng))

    def _plan_defaults(self, project, scope, cp_template, bin_template, customer_template):
        source = TripPlan.objects.filter(
            project_id=project.unique_id, is_deleted=False, staff_template_id__isnull=False,
        ).exclude(display_code__startswith=f"{NAME_PREFIX}-").first()
        staff_template_id = getattr(source, "staff_template_id", None) or getattr(
            StaffTemplate.objects.filter(**scope, is_deleted=False).first(), "unique_id", None
        )
        vehicle_id = getattr(source, "vehicle_id", None) or getattr(
            VehicleCreation.objects.filter(**scope, is_deleted=False).first(), "unique_id", None
        )
        if not (staff_template_id and vehicle_id):
            raise _Skip("needs a staff template and a vehicle")
        waste_type_ids = (getattr(source, "waste_type_ids", None) or [bin_template.wastetype_id])
        return {
            **scope,
            "district_id": getattr(source, "district_id", None) or cp_template.district_id,
            "city_id": getattr(source, "city_id", None) or cp_template.city_id,
            "zone_id": getattr(source, "zone_id", None) or customer_template.zone_id,
            "panchayat_id": getattr(source, "panchayat_id", None) or customer_template.panchayat_id,
            "ward_ids": customer_template.ward_id,
            "staff_template_id": staff_template_id,
            "vehicle_id": vehicle_id,
            "supervisor_id": getattr(source, "supervisor_id", None),
            "waste_type_id": waste_type_ids[0],
            "waste_type_ids": waste_type_ids,
            "waste_type_ids_csv": ",".join(waste_type_ids),
            "trip_trigger_weight_kg": getattr(source, "trip_trigger_weight_kg", None) or 800,
            "max_vehicle_capacity_kg": getattr(source, "max_vehicle_capacity_kg", None) or 3000,
            "scheduled_time": time(6, 0),
            "is_auto_assign": True,
            "repeat_days": [],
            "approval_status": TripPlan.ApprovalStatus.APPROVED,
            "status": TripPlan.Status.ACTIVE,
            "is_active": True,
            "is_deleted": False,
        }

    def _plan(self, display_code, collection_type, defaults):
        plan, _ = TripPlan.objects.update_or_create(
            display_code=display_code,
            defaults={**defaults, "collection_type": collection_type},
        )
        return plan

    def _collection_point(self, scope, cp_template, bin_template, name, lat, lng):
        cp_name = f"{NAME_PREFIX} · {name}"
        cp = Collection_point.objects.filter(**scope, cp_name=cp_name, is_deleted=False).first()
        if not cp:
            cp = Collection_point.objects.create(**{
                **_clone_kwargs(cp_template),
                "cp_name": cp_name,
                "collection_type": "bin_collection",
                "latitude": _coord(lat),
                "longitude": _coord(lng),
                "is_active": True,
                "is_deleted": False,
            })
        bin_ = Bins.objects.filter(collection_point_id=cp.unique_id, is_deleted=False).first()
        if not bin_:
            bin_ = Bins.objects.create(**{
                **_clone_kwargs(bin_template, skip=("bin_qr", "bin_image")),
                "collection_point_id": cp.unique_id,
                "bin_name": f"{name} Bin",
                "bin_qr": "",
                "bin_image": "",
                "is_active": True,
                "is_deleted": False,
            })
        return cp, bin_

    def _customer(self, scope, template, index, name, lat, lng):
        customer_name = f"{NAME_PREFIX} · {name}"
        customer = CustomerCreation.objects.filter(
            **scope, customer_name=customer_name, is_deleted=False,
        ).first()
        if customer:
            return customer
        return CustomerCreation.objects.create(**{
            **_clone_kwargs(template, skip=(
                "customer_id", "apartment_unique_id", "apartment_qr", "qr_code", "group_qr_id",
                "username", "password", "password_crt_date", "previous_password", "fcm_token",
            )),
            "customer_name": customer_name,
            "contact_no": f"90000{index:05d}"[-10:],
            "id_no": f"{NAME_PREFIX}-{scope['project_id'][-6:]}-{index:02d}",
            "latitude": f"{lat:.6f}",
            "longitude": f"{lng:.6f}",
            "apartment_name": "",
            "username": "",
            "password": "",
            "is_bulkwaste_generator": False,
            "is_active": True,
            "is_deleted": False,
        })

    def _replace_plan_stops(self, plan, stops):
        TripPlanCollectionPoint.objects.filter(trip_plan_id=plan.unique_id).delete()
        for sequence, stop in enumerate(stops, start=1):
            TripPlanCollectionPoint.objects.create(
                trip_plan_id=plan.unique_id,
                company_id=plan.company_id,
                project_id=plan.project_id,
                sequence=sequence,
                is_active=True,
                **stop,
            )

    def _detour(self, plan, after, before, key=None):
        """One plan detour on the leg `after` → `before`, pushed off the
        straight line — as if avoiding a closed road."""
        if RouteDetourWaypoint.objects.filter(trip_plan_id=plan.unique_id, is_deleted=False).exists():
            return
        lat = (float(after.latitude) + float(before.latitude)) / 2 + 0.0012
        lng = (float(after.longitude) + float(before.longitude)) / 2 - 0.0012
        RouteDetourWaypoint.objects.create(
            trip_plan_id=plan.unique_id,
            after_stop_id=key or cp_key(after.unique_id),
            sequence=1,
            latitude=_coord(lat),
            longitude=_coord(lng),
        )

    # ------------------------------------------------------------------
    # Today's trip
    # ------------------------------------------------------------------

    def _todays_trip(self, plan):
        today = timezone.localdate()
        trip = (
            DailyTripAssignment.objects.filter(trip_plan_id=plan.unique_id, trip_date=today, is_deleted=False)
            .order_by("created_at")
            .first()
        )
        if trip:
            return trip, False
        # Creating it runs the normal path: stops cloned from the plan and a
        # copy of the plan's saved static route taken.
        trip = DailyTripAssignment.objects.create(
            company_id=plan.company_id,
            project_id=plan.project_id,
            trip_plan_id=plan.unique_id,
            trip_date=today,
            scheduled_time=plan.scheduled_time,
            approval_status=DailyTripAssignment.APPROVAL_APPROVED,
        )
        return trip, True

    def _simulate_progress(self, trip, plan):
        started_at = timezone.make_aware(datetime.combine(trip.trip_date, plan.scheduled_time))
        trip.mark_started(at=started_at)

        is_bin = plan.collection_type == TripPlan.COLLECTION_TYPE_BIN
        model = DailyTripCollectionPoint if is_bin else DailyTripHouseholdCollection
        stops = list(model.objects.filter(trip_assignment_id=trip.unique_id, is_deleted=False).order_by("sequence"))
        collected = int(len(stops) * COLLECTED_SHARE)
        vehicle_id = trip.vehicle_id or plan.vehicle_id

        for index, stop in enumerate(stops):
            at = started_at + timedelta(minutes=MINUTES_PER_STOP * (index + 1))
            if index < collected:
                weight = Decimal(str(18 + (index * 7) % 23)) if is_bin else Decimal(str(2 + index % 4))
                model.objects.filter(pk=stop.pk).update(
                    status=model.STATUS_COLLECTED, is_collected=True,
                    collected_at=at, collected_weight_kg=weight,
                )
                if is_bin:
                    cp = stop.collection_point
                    BinCollectionEvent.objects.create(
                        company_id=trip.company_id, project_id=trip.project_id,
                        trip_assignment_id=trip.unique_id, trip_collection_point_id=stop.unique_id,
                        collection_point_id=stop.collection_point_id, bin_id=stop.bin_id,
                        panchayat_id=stop.panchayat_id, ward_id=stop.ward_id, zone_id=stop.zone_id,
                        waste_type_id=getattr(stop.bin, "wastetype_id", None), vehicle_id=vehicle_id,
                        collected_weight_kg=weight, status=BinCollectionEvent.STATUS_COLLECTED,
                        collection_date=trip.trip_date,
                        # Last scan = where the vehicle is now on the tracking map.
                        driver_latitude=cp.latitude, driver_longitude=cp.longitude,
                    )
            elif index == collected and is_bin:
                model.objects.filter(pk=stop.pk).update(status=model.STATUS_IN_PROGRESS)
            elif index == collected:
                # Households have no "in progress": the resident wasn't home.
                model.objects.filter(pk=stop.pk).update(
                    status=DailyTripHouseholdCollection.STATUS_MISSED,  # "Not Available"
                    status_reason="Door locked",
                )
        return f"in progress — {collected} of {len(stops)} stops collected"


class _Skip(Exception):
    pass
