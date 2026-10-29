"""Vehicle Status Dashboard — what each vehicle is doing on one day.

Two views over a `dashboard_metrics.Scope` whose `end` is the day looked at:

- `fleet_status(scope)`: one row per vehicle in scope — its state (on trip,
  broken down, ...), the trip it is on, crew, stops left and weight collected
  today and this month.
- `vehicle_status(scope, vehicle)`: everything about one vehicle — today's
  trips with start timings and start delay, its crew and alternative crew,
  breakdowns, re-trips and delay reports, stops collected/remaining per
  collection type and waste type, and weight today/this month split by
  collection type and waste type.

Weight attribution follows the Admin Dashboard (dashboard_metrics.operations):
bin weight is the Collected BinCollectionEvent rows, household/bulk weight the
WasteCollection rows. A bin event belongs to the vehicle that scanned it
(`vehicle_id`, which differs from the trip's vehicle after a breakdown
replacement); everything else belongs to its trip's vehicle.

Live GPS position is not here: it comes from the project's GPS provider and is
fetched by the browser (see the frontend's gpsApiConfig). `last_seen` is the
fallback — the latest geotagged scan/stop/breakdown recorded today.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.core_modules.daily_operations.wastecollection import WasteCollection
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.panchayat import Panchayat
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.ward import Ward
from app.models.masters.waste_masters.bins import Bins
from app.models.superadmin.staff_management.staffcreation import (
    StaffcreationOfficeDetails,
    StaffPersonalDetails,
)
from app.models.superadmin_masters.project import Project
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.services.dashboard_metrics import Scope, kg, pct, scoped

BIN = TripPlan.COLLECTION_TYPE_BIN
HOUSEHOLD = TripPlan.COLLECTION_TYPE_HOUSEHOLD
BULK = TripPlan.COLLECTION_TYPE_BULK
COLLECTION_TYPES = (BIN, HOUSEHOLD, BULK)

# Same grace as dashboard_metrics.operations() and the trip delay screen.
START_GRACE_MIN = 15

HOUSEHOLD_SPLIT = (
    ("Wet Waste", "wet"),
    ("Dry Waste", "dry"),
    ("Mixed Waste", "mixed"),
    ("Sanitary Waste", "sanitary"),
)

STATE_BREAKDOWN = "breakdown"
STATE_ON_TRIP = "on_trip"
STATE_SCHEDULED = "scheduled"
STATE_COMPLETED = "completed"
STATE_IDLE = "idle"
STATES = (STATE_ON_TRIP, STATE_BREAKDOWN, STATE_SCHEDULED, STATE_COMPLETED, STATE_IDLE)

OPEN_DELAY = (TripDelayReport.STATUS_REPORTED, TripDelayReport.STATUS_ACKNOWLEDGED)


# ----------------------------------------------------------------- helpers

def _day_window(start, end):
    """Aware [start, end + 1 day) datetimes."""
    return Scope(None, None, start, end).window


def _hhmm(value):
    return value.strftime("%H:%M") if value else None


def _iso(value):
    return timezone.localtime(value).isoformat() if value else None


def _float(value):
    return float(value) if value is not None else None


def _ids(csv):
    return [v for v in (csv or "").split(",") if v]


def _stop_bucket(status, carried, *, collected, missed):
    """collected / missed / carried (moved to a re-trip or replacement trip) /
    remaining. A carried stop keeps its Pending status on the source trip, so
    it must not count as remaining there as well."""
    if status == collected:
        return "collected"
    if status in missed:
        return "missed"
    if carried:
        return "carried"
    return "remaining"


def _empty_stops():
    return {"planned": 0, "collected": 0, "remaining": 0, "missed": 0, "carried": 0}


def _add_stop(bucket_counts, bucket):
    bucket_counts["planned"] += 1
    bucket_counts[bucket] += 1


def _with_rate(stops):
    return {**stops, "completion_rate": pct(stops["collected"], stops["planned"])}


def _start_timing(trip, day, now):
    """Start delay against the scheduled time. `late` uses the same 15 minute
    grace as the Admin Dashboard; a trip not started yet is `overdue_min`
    late once that grace has passed (only meaningful for today)."""
    if not trip.scheduled_time:
        return {"start_delay_min": None, "late": False, "overdue_min": None}
    tz = timezone.get_current_timezone()
    scheduled = timezone.make_aware(datetime.combine(trip.trip_date, trip.scheduled_time), tz)
    if trip.actual_start_at:
        delay = int((trip.actual_start_at - scheduled).total_seconds() // 60)
        return {"start_delay_min": delay, "late": delay > START_GRACE_MIN, "overdue_min": None}
    overdue = None
    if trip.status == DailyTripAssignment.STATUS_SCHEDULED and trip.trip_date == day:
        late_by = int((now - scheduled).total_seconds() // 60)
        if late_by > START_GRACE_MIN:
            overdue = late_by
    return {"start_delay_min": None, "late": overdue is not None, "overdue_min": overdue}


def _duration_min(trip, now):
    if not trip.actual_start_at:
        return None
    end = trip.actual_end_at or now
    return max(int((end - trip.actual_start_at).total_seconds() // 60), 0)


def _current_trip(trips):
    """The trip a vehicle is on: In Progress, else the next Scheduled, else
    the last Completed."""
    live_trips = [t for t in trips if t.status != DailyTripAssignment.STATUS_CANCELLED]
    for status, last in (
        (DailyTripAssignment.STATUS_IN_PROGRESS, False),
        (DailyTripAssignment.STATUS_SCHEDULED, False),
        (DailyTripAssignment.STATUS_COMPLETED, True),
    ):
        matching = sorted(
            (t for t in live_trips if t.status == status),
            key=lambda t: (t.scheduled_time or datetime.min.time(), t.created_at or timezone.now()),
        )
        if matching:
            return matching[-1] if last else matching[0]
    return None


def _repaired_by(breakdown, day):
    """The broken vehicle was back in service by the end of `day`."""
    return bool(breakdown.repaired_at) and timezone.localdate(breakdown.repaired_at) <= day


def _state(trips, broken_down):
    if broken_down:
        return STATE_BREAKDOWN
    statuses = {t.status for t in trips}
    if DailyTripAssignment.STATUS_IN_PROGRESS in statuses:
        return STATE_ON_TRIP
    if DailyTripAssignment.STATUS_SCHEDULED in statuses:
        return STATE_SCHEDULED
    if DailyTripAssignment.STATUS_COMPLETED in statuses:
        return STATE_COMPLETED
    return STATE_IDLE


class _Names:
    """Batched id -> display name lookups."""

    def __init__(self):
        self.waste_types = dict(WasteType.objects.values_list("unique_id", "waste_type_name"))
        self.vehicle_types = dict(VehicleTypeCreation.objects.values_list("unique_id", "vehicleType"))
        self._staff = {}
        self._plans = {}

    def waste(self, waste_type_id):
        return self.waste_types.get(waste_type_id) or "Unclassified"

    def load_plans(self, plan_ids):
        missing = set(plan_ids) - set(self._plans) - {None, ""}
        for plan in TripPlan.objects.filter(unique_id__in=missing):
            self._plans[plan.unique_id] = plan

    def plan(self, plan_id):
        return self._plans.get(plan_id)

    def plan_type(self, plan_id):
        plan = self._plans.get(plan_id)
        return plan.collection_type if plan else None

    def load_staff(self, staff_ids):
        missing = set(staff_ids) - set(self._staff) - {None, ""}
        if not missing:
            return
        mobiles = dict(
            StaffPersonalDetails.objects.filter(staff_unique_id__in=missing).values_list(
                "staff_unique_id", "contact_mobile",
            )
        )
        for staff_id, name, designation, emp_id in StaffcreationOfficeDetails.objects.filter(
            staff_unique_id__in=missing,
        ).values_list("staff_unique_id", "employee_name", "designation", "emp_id"):
            self._staff[staff_id] = {
                "id": staff_id,
                "name": name,
                "emp_id": emp_id,
                "designation": designation,
                "mobile": mobiles.get(staff_id),
            }

    def staff(self, staff_id):
        if not staff_id:
            return None
        return self._staff.get(staff_id) or {
            "id": staff_id, "name": staff_id, "emp_id": None, "designation": None, "mobile": None,
        }


def _crew_ids(template):
    if not template:
        return []
    extras = template.extra_operator_id if isinstance(template.extra_operator_id, list) else []
    return [template.driver_id, template.operator_id, *extras]


def _crew(template, names):
    """Driver, operator and extra operators of a staff / alternative staff
    template."""
    if not template:
        return None
    extras = template.extra_operator_id if isinstance(template.extra_operator_id, list) else []
    return {
        "template_id": template.unique_id,
        "code": template.display_code,
        "driver": names.staff(template.driver_id),
        "operator": names.staff(template.operator_id),
        "extra_operators": [names.staff(s) for s in extras if s],
    }


def _alt_crew(template, names):
    crew = _crew(template, names)
    if not crew:
        return None
    return {
        **crew,
        "staff_template_id": template.staff_template_id,
        "from_date": template.from_date.isoformat() if template.from_date else None,
        "to_date": template.to_date.isoformat() if template.to_date else None,
        "reason": template.change_reason,
        "remarks": template.change_remarks,
        "approval_status": template.approval_status,
    }


def _assignment_rows(ids):
    """{assignment_id: (vehicle_id, trip_plan_id)} for trips outside the
    month window that weighments still point at."""
    if not ids:
        return {}
    return {
        uid: (vehicle_id, plan_id)
        for uid, vehicle_id, plan_id in DailyTripAssignment.objects.filter(
            unique_id__in=ids,
        ).values_list("unique_id", "vehicle_id", "trip_plan_id")
    }


def _weighments(scope, start, end, assignments, names, vehicle_ids=None):
    """Collected weight as (vehicle_id, assignment_id, day, collection_type,
    waste_type_name, kg) tuples. `assignments` maps assignment_id ->
    (vehicle_id, trip_plan_id) and is extended in place with any trip a
    weighment references that is not in it yet."""
    bins = scoped(
        BinCollectionEvent.objects.filter(
            is_deleted=False,
            status=BinCollectionEvent.STATUS_COLLECTED,
            collection_date__gte=start,
            collection_date__lte=end,
        ),
        scope,
    )
    households = scoped(
        WasteCollection.objects.filter(
            is_deleted=False,
            collection_date__gte=start,
            collection_date__lte=end,
            trip_assignment_id__isnull=False,
        ),
        scope,
    )
    if vehicle_ids is not None:
        trip_ids = [uid for uid, (vid, _) in assignments.items() if vid in vehicle_ids]
        bins = bins.filter(Q(vehicle_id__in=vehicle_ids) | Q(trip_assignment_id__in=trip_ids))
        households = households.filter(trip_assignment_id__in=trip_ids)

    bin_rows = list(
        bins.order_by()
        .values("trip_assignment_id", "vehicle_id", "waste_type_id", "collection_date")
        .annotate(kg=Sum("collected_weight_kg"))
    )
    household_rows = list(
        households.order_by()
        .values("trip_assignment_id", "collection_date")
        .annotate(
            total=Sum("total_quantity"),
            wet=Sum("wet_waste"),
            dry=Sum("dry_waste"),
            mixed=Sum("mixed_waste"),
            sanitary=Sum("sanitary_waste"),
        )
    )
    referenced = {r["trip_assignment_id"] for r in bin_rows + household_rows} - {None}
    assignments.update(_assignment_rows(referenced - set(assignments)))
    names.load_plans(plan_id for _, plan_id in assignments.values())

    out = []
    for row in bin_rows:
        trip_id = row["trip_assignment_id"]
        vehicle_id = row["vehicle_id"] or assignments.get(trip_id, (None, None))[0]
        if vehicle_id:
            out.append((
                vehicle_id, trip_id, row["collection_date"], BIN,
                names.waste(row["waste_type_id"]), kg(row["kg"]),
            ))
    for row in household_rows:
        trip_id = row["trip_assignment_id"]
        vehicle_id, plan_id = assignments.get(trip_id, (None, None))
        if not vehicle_id:
            continue
        ctype = names.plan_type(plan_id)
        ctype = ctype if ctype in (HOUSEHOLD, BULK) else HOUSEHOLD
        classified = 0.0
        for label, field in HOUSEHOLD_SPLIT:
            value = kg(row[field])
            classified += value
            if value:
                out.append((vehicle_id, trip_id, row["collection_date"], ctype, label, value))
        rest = round(kg(row["total"]) - classified, 2)
        if rest > 0:
            out.append((vehicle_id, trip_id, row["collection_date"], ctype, "Unclassified", rest))
    return out


def _weight_summary(rows):
    by_type = Counter()
    by_waste = Counter()
    by_type_waste = defaultdict(Counter)
    for _, _, _, ctype, waste, value in rows:
        by_type[ctype] += value
        by_waste[waste] += value
        by_type_waste[ctype][waste] += value
    total = round(sum(by_type.values()), 2)
    return {
        "total_kg": total,
        "by_collection_type": {c: round(by_type.get(c, 0), 2) for c in COLLECTION_TYPES},
        "by_waste_type": [
            {"name": name, "kg": round(value, 2), "share": pct(value, total)}
            for name, value in by_waste.most_common()
            if value > 0
        ],
        "by_collection_and_waste_type": {
            ctype: [
                {"name": name, "kg": round(value, 2)}
                for name, value in by_type_waste[ctype].most_common()
                if value > 0
            ]
            for ctype in COLLECTION_TYPES
        },
    }


def _stops_by_trip(trip_ids):
    """{trip_id: {collection_type: stop counts}} for bin and household/bulk
    stops of the given trips."""
    out = defaultdict(lambda: defaultdict(_empty_stops))
    for trip_id, status, carried in DailyTripCollectionPoint.objects.filter(
        is_deleted=False, trip_assignment_id__in=trip_ids,
    ).values_list("trip_assignment_id", "status", "carried_to_assignment"):
        _add_stop(out[trip_id][BIN], _stop_bucket(
            status, carried,
            collected=DailyTripCollectionPoint.STATUS_COLLECTED,
            missed=(DailyTripCollectionPoint.STATUS_MISSED,),
        ))
    for trip_id, ctype, status, carried in DailyTripHouseholdCollection.objects.filter(
        is_deleted=False, trip_assignment_id__in=trip_ids,
    ).values_list("trip_assignment_id", "collection_type", "status", "carried_to_assignment"):
        _add_stop(out[trip_id][ctype if ctype == BULK else HOUSEHOLD], _stop_bucket(
            status, carried,
            collected=DailyTripHouseholdCollection.STATUS_COLLECTED,
            missed=(
                DailyTripHouseholdCollection.STATUS_MISSED,
                DailyTripHouseholdCollection.STATUS_NOT_COLLECTED,
            ),
        ))
    return out


def _sum_stops(per_type_maps):
    total = _empty_stops()
    for per_type in per_type_maps:
        for counts in per_type.values():
            for key in total:
                total[key] += counts[key]
    return total


# ------------------------------------------------------------- fleet view

def supervised_vehicles(supervisor_ids):
    """Vehicles under a supervisor: named as its supervisor on the vehicle
    master, or run on a trip plan the supervisor owns — the two places the
    Vehicle master and the trip/breakdown/re-trip screens scope supervisors
    by. `supervisor_ids` holds every id the supervisor's records may use
    (staff_unique_id, and the login unique_id the vehicle master accepts)."""
    ids = [i for i in supervisor_ids if i]
    return VehicleCreation.objects.filter(
        Q(supervisor_id__in=ids)
        | Q(unique_id__in=TripPlan.objects.filter(
            supervisor_id__in=ids, is_deleted=False,
        ).values("vehicle_id"))
    )


def vehicles_in_scope(scope, supervisor_ids=None):
    """Vehicles of the scope; only a supervisor's own when `supervisor_ids`
    is given."""
    qs = scoped(VehicleCreation.objects.filter(is_deleted=False), scope)
    if supervisor_ids is not None:
        qs = qs.filter(unique_id__in=supervised_vehicles(supervisor_ids).values("unique_id"))
    return qs.order_by("vehicle_no")


def fleet_status(scope, supervisor_ids=None):
    """One row per vehicle in scope for the day `scope.end`; only the
    vehicles a supervisor controls when `supervisor_ids` is given."""
    day = scope.end
    month_start = day.replace(day=1)
    now = timezone.localtime()
    names = _Names()

    vehicles = list(vehicles_in_scope(scope, supervisor_ids))
    names.load_staff({v.supervisor_id for v in vehicles})
    project_names = dict(
        Project.objects.filter(
            unique_id__in={v.project_id for v in vehicles if v.project_id},
        ).values_list("unique_id", "name")
    )

    month_trips = list(
        scoped(
            DailyTripAssignment.objects.filter(
                is_deleted=False, trip_date__gte=month_start, trip_date__lte=day,
            ),
            scope,
        )
    )
    assignments = {t.unique_id: (t.vehicle_id, t.trip_plan_id) for t in month_trips}
    today_trips = defaultdict(list)
    for trip in month_trips:
        if trip.trip_date == day and trip.vehicle_id:
            today_trips[trip.vehicle_id].append(trip)
    today_ids = [t.unique_id for trips in today_trips.values() for t in trips]
    names.load_plans({t.trip_plan_id for t in month_trips})
    names.load_staff({names.plan(t.trip_plan_id).supervisor_id for t in month_trips if names.plan(t.trip_plan_id)})

    # crews of the trip each vehicle is on
    current = {vid: _current_trip(trips) for vid, trips in today_trips.items()}
    templates = {
        t.unique_id: t
        for t in StaffTemplate.objects.filter(
            unique_id__in={c.staff_template_id for c in current.values() if c and c.staff_template_id},
        )
    }
    alt_templates = {
        t.unique_id: t
        for t in AlternativeStaffTemplate.objects.filter(
            unique_id__in={c.alt_staff_template_id for c in current.values() if c and c.alt_staff_template_id},
        )
    }
    names.load_staff(
        s
        for t in [*templates.values(), *alt_templates.values()]
        for s in _crew_ids(t)
    )

    stops = _stops_by_trip(today_ids)
    weighments = _weighments(scope, month_start, day, assignments, names)
    weight_today = Counter()
    weight_month = Counter()
    for vehicle_id, _, when, _, _, value in weighments:
        weight_month[vehicle_id] += value
        if when == day:
            weight_today[vehicle_id] += value

    start_dt, end_dt = _day_window(day, day)
    breakdowns = defaultdict(list)
    # A breakdown belongs to the day of the trip it was reported on, or to
    # the day it was reported when it has no trip.
    for b in scoped(
        VehicleBreakdown.objects.filter(
            Q(trip_assignment_id__in=today_ids)
            | Q(created_at__gte=start_dt, created_at__lt=end_dt),
            is_deleted=False,
        ).exclude(status=VehicleBreakdown.STATUS_REJECTED),
        scope,
    ):
        if b.breakdown_vehicle_id:
            breakdowns[b.breakdown_vehicle_id].append(b)
    broken_down = {
        vehicle_id
        for vehicle_id, rows in breakdowns.items()
        if any(not _repaired_by(b, day) for b in rows)
    }
    trip_vehicle = {t.unique_id: t.vehicle_id for trips in today_trips.values() for t in trips}
    delays = defaultdict(list)
    for d in TripDelayReport.objects.filter(is_deleted=False, trip_assignment_id__in=today_ids):
        delays[trip_vehicle[d.trip_assignment_id]].append(d)
    retrips = defaultdict(list)
    for r in TripRetripRequest.objects.filter(is_deleted=False, assignment_id__in=today_ids):
        retrips[trip_vehicle[r.assignment_id]].append(r)

    rows = []
    for v in vehicles:
        trips = today_trips.get(v.unique_id, [])
        trip = current.get(v.unique_id)
        statuses = Counter(t.status for t in trips)
        starts = [_start_timing(t, day, now) for t in trips]
        vehicle_stops = _sum_stops(stops[t.unique_id] for t in trips if t.unique_id in stops)
        template = templates.get(trip.staff_template_id) if trip else None
        alt = alt_templates.get(trip.alt_staff_template_id) if trip else None
        crew = alt or template
        scheduled = sorted(t.scheduled_time for t in trips if t.scheduled_time)
        started = sorted(t.actual_start_at for t in trips if t.actual_start_at)
        open_breakdowns = [
            b for b in breakdowns.get(v.unique_id, [])
            if b.status == VehicleBreakdown.STATUS_REPORTED
        ]
        rows.append({
            "vehicle_id": v.unique_id,
            "vehicle_no": v.vehicle_no,
            "vehicle_type": names.vehicle_types.get(v.vehicle_type_id),
            "capacity": _float(v.capacity),
            "project_id": v.project_id,
            "project_name": project_names.get(v.project_id),
            "state": _state(trips, v.unique_id in broken_down),
            "operational_status": v.operational_status,
            "current_trip": _trip_brief(trip, names, now, day) if trip else None,
            "trips": {
                "total": len(trips),
                "completed": statuses.get(DailyTripAssignment.STATUS_COMPLETED, 0),
                "in_progress": statuses.get(DailyTripAssignment.STATUS_IN_PROGRESS, 0),
                "scheduled": statuses.get(DailyTripAssignment.STATUS_SCHEDULED, 0),
                "cancelled": statuses.get(DailyTripAssignment.STATUS_CANCELLED, 0),
                "late_starts": sum(1 for s in starts if s["late"]),
            },
            "first_scheduled_time": _hhmm(scheduled[0]) if scheduled else None,
            "first_start_at": _iso(started[0]) if started else None,
            # The vehicle master's supervisor; the trip plan's is on current_trip.
            "supervisor": names.staff(v.supervisor_id),
            "driver": names.staff(crew.driver_id) if crew else None,
            "operator": names.staff(crew.operator_id) if crew else None,
            "on_alternative_staff": bool(alt),
            "stops": _with_rate(vehicle_stops),
            "weight_today_kg": round(weight_today.get(v.unique_id, 0), 2),
            "weight_month_kg": round(weight_month.get(v.unique_id, 0), 2),
            "breakdowns": len(breakdowns.get(v.unique_id, [])),
            "open_breakdowns": len(open_breakdowns),
            "delays": len(delays.get(v.unique_id, [])),
            "open_delays": sum(1 for d in delays.get(v.unique_id, []) if d.status in OPEN_DELAY),
            "delay_minutes": sum(d.estimated_delay_minutes or 0 for d in delays.get(v.unique_id, [])),
            "retrips": len(retrips.get(v.unique_id, [])),
            "pending_retrips": sum(
                1 for r in retrips.get(v.unique_id, [])
                if r.status == TripRetripRequest.STATUS_PENDING
            ),
        })

    stop_totals = _sum_stops([{"all": r["stops"]} for r in rows])
    states = Counter(r["state"] for r in rows)
    return {
        "date": day.isoformat(),
        "month_start": month_start.isoformat(),
        "summary": {
            "vehicles": len(rows),
            "states": {s: states.get(s, 0) for s in STATES},
            "trips": sum(r["trips"]["total"] for r in rows),
            "trips_completed": sum(r["trips"]["completed"] for r in rows),
            "late_starts": sum(r["trips"]["late_starts"] for r in rows),
            "stops": _with_rate(stop_totals),
            "weight_today_kg": round(sum(r["weight_today_kg"] for r in rows), 2),
            "weight_month_kg": round(sum(r["weight_month_kg"] for r in rows), 2),
            "breakdowns": sum(r["breakdowns"] for r in rows),
            "delays": sum(r["delays"] for r in rows),
            "retrips": sum(r["retrips"] for r in rows),
            "on_alternative_staff": sum(1 for r in rows if r["on_alternative_staff"]),
        },
        "vehicles": rows,
    }


def _trip_brief(trip, names, now, day):
    plan = names.plan(trip.trip_plan_id)
    return {
        "id": trip.unique_id,
        "plan_code": plan.display_code if plan else None,
        "supervisor": names.staff(plan.supervisor_id) if plan else None,
        "collection_type": plan.collection_type if plan else None,
        "status": trip.status,
        "scheduled_time": _hhmm(trip.scheduled_time),
        "actual_start_at": _iso(trip.actual_start_at),
        "actual_end_at": _iso(trip.actual_end_at),
        **_start_timing(trip, day, now),
    }


# ----------------------------------------------------------- vehicle view

def _last_seen(vehicle_id, trip_ids, day):
    """Latest geotagged event of the day: a bin scan, a household stop
    update or a breakdown report."""
    start_dt, end_dt = _day_window(day, day)
    candidates = []
    scan = (
        BinCollectionEvent.objects.filter(
            Q(vehicle_id=vehicle_id) | Q(trip_assignment_id__in=trip_ids),
            is_deleted=False,
            collection_date=day,
            driver_latitude__isnull=False,
            driver_longitude__isnull=False,
        )
        .order_by("-created_at")
        .values_list("created_at", "driver_latitude", "driver_longitude")
        .first()
    )
    if scan:
        candidates.append((scan[0], scan[1], scan[2], "bin_scan"))
    stop = (
        DailyTripHouseholdCollection.objects.filter(
            is_deleted=False,
            trip_assignment_id__in=trip_ids,
            status_latitude__isnull=False,
            status_longitude__isnull=False,
        )
        .order_by("-updated_at")
        .values_list("updated_at", "status_latitude", "status_longitude")
        .first()
    )
    if stop and stop[0]:
        candidates.append((stop[0], stop[1], stop[2], "household_stop"))
    breakdown = (
        VehicleBreakdown.objects.filter(
            Q(trip_assignment_id__in=trip_ids) | Q(created_at__gte=start_dt, created_at__lt=end_dt),
            is_deleted=False,
            breakdown_vehicle_id=vehicle_id,
            breakdown_lat__isnull=False,
            breakdown_lng__isnull=False,
        )
        .order_by("-created_at")
        .values_list("created_at", "breakdown_lat", "breakdown_lng")
        .first()
    )
    if breakdown:
        candidates.append((breakdown[0], breakdown[1], breakdown[2], "breakdown"))
    if not candidates:
        return None
    at, lat, lng, source = max(candidates, key=lambda c: c[0])
    return {"lat": float(lat), "lng": float(lng), "at": _iso(at), "source": source}


def _stops_by_waste_type(trips, names):
    """Today's stops per waste type: a bin stop takes its bin's waste type; a
    household/bulk stop the waste types of its trip."""
    out = defaultdict(_empty_stops)
    trip_ids = [t.unique_id for t in trips]
    trip_waste = {
        t.unique_id: ", ".join(
            names.waste(w)
            for w in (t.get_household_waste_type_ids() or t.get_waste_type_ids() or t.waste_type_ids or [])
        ) or "Unclassified"
        for t in trips
    }
    points = list(
        DailyTripCollectionPoint.objects.filter(
            is_deleted=False, trip_assignment_id__in=trip_ids,
        ).values_list("bin_id", "status", "carried_to_assignment")
    )
    bin_waste = dict(
        Bins.objects.filter(unique_id__in={p[0] for p in points if p[0]}).values_list(
            "unique_id", "wastetype_id",
        )
    )
    for bin_id, status, carried in points:
        _add_stop(out[names.waste(bin_waste.get(bin_id))], _stop_bucket(
            status, carried,
            collected=DailyTripCollectionPoint.STATUS_COLLECTED,
            missed=(DailyTripCollectionPoint.STATUS_MISSED,),
        ))
    for trip_id, status, carried in DailyTripHouseholdCollection.objects.filter(
        is_deleted=False, trip_assignment_id__in=trip_ids,
    ).values_list("trip_assignment_id", "status", "carried_to_assignment"):
        _add_stop(out[trip_waste[trip_id]], _stop_bucket(
            status, carried,
            collected=DailyTripHouseholdCollection.STATUS_COLLECTED,
            missed=(
                DailyTripHouseholdCollection.STATUS_MISSED,
                DailyTripHouseholdCollection.STATUS_NOT_COLLECTED,
            ),
        ))
    return [{"name": name, **_with_rate(counts)} for name, counts in sorted(out.items())]


def vehicle_status(scope, vehicle):
    """Everything about one vehicle for the day `scope.end` and its month."""
    day = scope.end
    month_start = day.replace(day=1)
    now = timezone.localtime()
    names = _Names()

    month_trips = list(
        DailyTripAssignment.objects.filter(
            is_deleted=False,
            vehicle_id=vehicle.unique_id,
            trip_date__gte=month_start,
            trip_date__lte=day,
        ).order_by("trip_date", "scheduled_time", "created_at")
    )
    trips = [t for t in month_trips if t.trip_date == day]
    trip_ids = [t.unique_id for t in trips]
    month_ids = [t.unique_id for t in month_trips]
    names.load_plans({t.trip_plan_id for t in month_trips})
    names.load_staff(
        {vehicle.supervisor_id}
        | {names.plan(t.trip_plan_id).supervisor_id for t in trips if names.plan(t.trip_plan_id)}
    )

    # Re-trip number: position among same-plan trips of the day (any vehicle,
    # a continuation may run on a replacement vehicle).
    siblings = defaultdict(list)
    for uid, plan_id, created in DailyTripAssignment.objects.filter(
        is_deleted=False,
        trip_date=day,
        trip_plan_id__in={t.trip_plan_id for t in trips if t.trip_plan_id},
    ).order_by("created_at", "unique_id").values_list("unique_id", "trip_plan_id", "created_at"):
        siblings[plan_id].append(uid)

    # ---- crew: today's trips, the vehicle's trip plans, and alternatives
    plan_template_ids = set(
        TripPlan.objects.filter(
            is_deleted=False, vehicle_id=vehicle.unique_id, status=TripPlan.Status.ACTIVE,
        ).values_list("staff_template_id", flat=True)
    )
    template_ids = (plan_template_ids | {t.staff_template_id for t in trips}) - {None, ""}
    templates = {t.unique_id: t for t in StaffTemplate.objects.filter(unique_id__in=template_ids)}
    alternatives = {
        a.unique_id: a
        for a in AlternativeStaffTemplate.objects.filter(
            Q(staff_template_id__in=template_ids,
              is_deleted=False,
              approval_status__in=("APPROVED", "PENDING"))
            & (Q(from_date__isnull=True) | Q(from_date__lte=day))
            & (Q(to_date__isnull=True) | Q(to_date__gte=day))
            | Q(unique_id__in={t.alt_staff_template_id for t in trips if t.alt_staff_template_id})
        )
    }
    names.load_staff(
        s for t in [*templates.values(), *alternatives.values()] for s in _crew_ids(t)
    )

    # ---- stops and weight
    stops = _stops_by_trip(trip_ids)
    assignments = {t.unique_id: (t.vehicle_id, t.trip_plan_id) for t in month_trips}
    weighments = _weighments(
        scope, month_start, day, assignments, names, vehicle_ids={vehicle.unique_id},
    )
    weighments = [w for w in weighments if w[0] == vehicle.unique_id]
    today_weighments = [w for w in weighments if w[2] == day]
    trip_weight = Counter()
    for _, trip_id, when, _, _, value in today_weighments:
        trip_weight[trip_id] += value
    daily_weight = Counter()
    for _, _, when, _, _, value in weighments:
        daily_weight[when] += value

    # ---- exceptions
    month_start_dt, end_dt = _day_window(month_start, day)
    breakdowns = list(
        VehicleBreakdown.objects.filter(
            Q(breakdown_vehicle_id=vehicle.unique_id) | Q(replacement_vehicle_id=vehicle.unique_id),
            Q(trip_assignment_id__in=month_ids)
            | Q(new_assignment__in=month_ids)
            | Q(created_at__gte=month_start_dt, created_at__lt=end_dt),
            is_deleted=False,
        ).order_by("-created_at")
    )
    breakdown_trips = dict(
        DailyTripAssignment.objects.filter(
            unique_id__in={b.trip_assignment_id for b in breakdowns},
        ).values_list("unique_id", "trip_date")
    )

    def breakdown_day(b):
        return breakdown_trips.get(b.trip_assignment_id) or timezone.localdate(b.created_at)
    delays = list(
        TripDelayReport.objects.filter(
            is_deleted=False, trip_assignment_id__in=month_ids,
        ).order_by("-created_at")
    )
    retrips = list(
        TripRetripRequest.objects.filter(
            is_deleted=False, assignment_id__in=month_ids,
        ).order_by("-created_at")
    )
    other_vehicles = dict(
        VehicleCreation.objects.filter(
            unique_id__in={b.replacement_vehicle_id for b in breakdowns}
            | {b.breakdown_vehicle_id for b in breakdowns},
        ).values_list("unique_id", "vehicle_no")
    )
    names.load_staff(
        {r.requested_by_id for r in retrips}
        | {d.reported_by_id for d in delays}
        | {b.replacement_driver_id for b in breakdowns}
        | {b.replacement_operator_id for b in breakdowns}
    )
    trip_dates = {t.unique_id: t.trip_date for t in month_trips}

    wards = dict(
        Ward.objects.filter(
            unique_id__in={w for t in trips for w in t.get_ward_ids()},
        ).values_list("unique_id", "ward_name")
    )
    panchayats = dict(
        Panchayat.objects.filter(
            unique_id__in={t.panchayat_id for t in trips if t.panchayat_id},
        ).values_list("unique_id", "panchayat_name")
    )

    def trip_row(t):
        plan = names.plan(t.trip_plan_id)
        trip_stops = stops.get(t.unique_id, {})
        template = templates.get(t.staff_template_id)
        alt = alternatives.get(t.alt_staff_template_id)
        sequence = siblings.get(t.trip_plan_id, [])
        return {
            "id": t.unique_id,
            "trip_number": sequence.index(t.unique_id) + 1 if t.unique_id in sequence else 1,
            "plan_id": t.trip_plan_id,
            "plan_code": plan.display_code if plan else None,
            "supervisor": names.staff(plan.supervisor_id) if plan else None,
            "collection_type": plan.collection_type if plan else None,
            "waste_types": [
                names.waste(w) for w in (t.get_waste_type_ids() or t.waste_type_ids or [])
            ],
            "panchayat": panchayats.get(t.panchayat_id),
            "wards": [wards.get(w, w) for w in t.get_ward_ids()],
            "status": t.status,
            "approval_status": t.approval_status,
            "scheduled_time": _hhmm(t.scheduled_time),
            "actual_start_at": _iso(t.actual_start_at),
            "actual_end_at": _iso(t.actual_end_at),
            "duration_min": _duration_min(t, now),
            **_start_timing(t, day, now),
            "stops": {
                ctype: _with_rate(counts) for ctype, counts in trip_stops.items()
            },
            "stops_total": _with_rate(_sum_stops([trip_stops])),
            "weight_kg": round(trip_weight.get(t.unique_id, 0), 2),
            "staff": _crew(template, names),
            "alternative_staff": _alt_crew(alt, names),
            "remarks": t.remarks,
        }

    stops_by_type = defaultdict(_empty_stops)
    for per_type in stops.values():
        for ctype, counts in per_type.items():
            for key in counts:
                stops_by_type[ctype][key] += counts[key]

    current = _current_trip(trips)
    open_breakdown = any(
        b.breakdown_vehicle_id == vehicle.unique_id
        and breakdown_day(b) == day
        and b.status != VehicleBreakdown.STATUS_REJECTED
        and not _repaired_by(b, day)
        for b in breakdowns
    )
    project = Project.objects.filter(unique_id=vehicle.project_id).first()

    return {
        "date": day.isoformat(),
        "month_start": month_start.isoformat(),
        "vehicle": {
            "id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "vehicle_type": names.vehicle_types.get(vehicle.vehicle_type_id),
            "capacity": _float(vehicle.capacity),
            "condition": vehicle.vehicle_condition,
            "operational_status": vehicle.operational_status,
            "insurance_expiry_date": (
                vehicle.insurance_expiry_date.isoformat() if vehicle.insurance_expiry_date else None
            ),
            "project_id": vehicle.project_id,
            "project_name": project.name if project else None,
            "is_active": vehicle.is_active,
            "supervisor": names.staff(vehicle.supervisor_id),
        },
        "state": _state(trips, open_breakdown),
        "current_trip_id": current.unique_id if current else None,
        "last_seen": _last_seen(vehicle.unique_id, trip_ids, day),
        "trips": [trip_row(t) for t in trips],
        "month_trips": {
            "total": len(month_trips),
            "completed": sum(
                1 for t in month_trips if t.status == DailyTripAssignment.STATUS_COMPLETED
            ),
            "late_starts": sum(1 for t in month_trips if _start_timing(t, day, now)["late"]),
        },
        "staff": {
            "assigned": [_crew(t, names) for t in templates.values()],
            "alternatives": [_alt_crew(a, names) for a in alternatives.values()],
        },
        "stops": {
            "total": _with_rate(_sum_stops([stops_by_type])),
            "by_collection_type": {
                ctype: _with_rate(stops_by_type[ctype]) for ctype in COLLECTION_TYPES
            },
            "by_waste_type": _stops_by_waste_type(trips, names),
        },
        "weight": {
            "today": _weight_summary(today_weighments),
            "month": _weight_summary(weighments),
            "daily": [
                {"date": d.isoformat(), "kg": round(daily_weight.get(d, 0), 2)}
                for d in (
                    month_start + timedelta(days=i)
                    for i in range((day - month_start).days + 1)
                )
            ],
        },
        "breakdowns": [
            {
                "id": b.unique_id,
                "trip_id": b.trip_assignment_id,
                "role": "broke_down" if b.breakdown_vehicle_id == vehicle.unique_id else "replacement",
                "date": breakdown_day(b).isoformat(),
                "reported_at": _iso(b.created_at),
                "time": _hhmm(b.breakdown_time),
                "reason": b.breakdown_reason,
                "remarks": b.breakdown_remarks,
                "location": b.breakdown_location,
                "lat": _float(b.breakdown_lat),
                "lng": _float(b.breakdown_lng),
                "status": b.status,
                "approval_status": b.approval_status,
                "repaired_at": _iso(b.repaired_at),
                "repair_remarks": b.repair_remarks,
                "broken_vehicle_no": other_vehicles.get(b.breakdown_vehicle_id),
                "replacement_vehicle_no": other_vehicles.get(b.replacement_vehicle_id),
                "replacement_driver": names.staff(b.replacement_driver_id),
                "replacement_operator": names.staff(b.replacement_operator_id),
                "collected_before_kg": _float(b.collected_weight_before_breakdown_kg),
                "continuation_trip_id": b.new_assignment,
            }
            for b in breakdowns
        ],
        "retrips": [
            {
                "id": r.unique_id,
                "trip_id": r.assignment_id,
                "trip_date": trip_dates[r.assignment_id].isoformat(),
                "requested_at": _iso(r.created_at),
                "requested_by": names.staff(r.requested_by_id),
                "reason": r.reason,
                "status": r.status,
                "pending_bins": r.pending_bin_count,
                "pending_households": r.pending_household_count,
                "reviewed_at": _iso(r.reviewed_at),
                "review_remarks": r.review_remarks,
                "continuation_trip_id": r.new_assignment_id,
            }
            for r in retrips
        ],
        "delays": [
            {
                "id": d.unique_id,
                "trip_id": d.trip_assignment_id,
                "trip_date": trip_dates[d.trip_assignment_id].isoformat(),
                "reported_at": _iso(d.created_at),
                "reported_by": names.staff(d.reported_by_id),
                "time": _hhmm(d.delay_time),
                "reason": d.delay_reason,
                "remarks": d.delay_remarks,
                "estimated_minutes": d.estimated_delay_minutes,
                "location": d.delay_location,
                "status": d.status,
                "supervisor_remarks": d.supervisor_remarks,
            }
            for d in delays
        ],
    }
