"""KPIs shared by the Admin and Superadmin dashboards.

Everything here works on a `Scope`: the companies and projects a caller may
see plus an inclusive date range. `None` for companies/projects means "no
restriction" (platform super admin looking at every tenant).

Tenancy columns are plain CharFields holding the parent's unique_id, so all
scoping is `company_id__in` / `project_id__in` — no joins.

Day buckets for DateTimeFields are computed in Python from an aware
[start, end) window rather than with TruncDate / `__date`: on MySQL those
need the server's time zone tables, which a fresh install does not load.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from types import SimpleNamespace
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from app.models.core_modules.attendance.attendance import Recognized
from app.models.core_modules.attendance.attendance_new import AttendanceNew
from app.models.core_modules.complaint_management.masters import (
    ComplaintCategory,
    ComplaintSlaRule,
    ComplaintStatus,
    ComplaintSubcategory,
)
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.core_modules.daily_operations.wastecollection import WasteCollection
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.block_panchayat_union import BlockPanchayatUnion
from app.models.masters.city import City
from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.district import District
from app.models.masters.leader_management.district_leader_login import DistrictLeaderLogin
from app.models.masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.panchayat import Panchayat
from app.models.masters.plant import Plant
from app.models.masters.transport_masters.fuel import Fuel
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.waste_masters.bins import Bins
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.projectStaffHierarchy import ProjectStaffHierarchy
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.staff_management.department import Department
from app.models.superadmin.staff_management.designation import Designation
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType

MAX_RANGE_DAYS = 366


# ------------------------------------------------------------------ scope

@dataclass(frozen=True)
class Scope:
    company_ids: tuple | None  # None = every company
    project_ids: tuple | None  # None = every project of those companies
    start: date
    end: date  # inclusive

    @property
    def days(self):
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]

    @property
    def window(self):
        """Aware [start, end) datetimes covering the date range."""
        tz = timezone.get_current_timezone()
        return (
            timezone.make_aware(datetime.combine(self.start, time.min), tz),
            timezone.make_aware(datetime.combine(self.end + timedelta(days=1), time.min), tz),
        )


def parse_range(params):
    """`date` (one day) or `from_date`/`to_date` (inclusive). Defaults to
    today. The range is clamped to MAX_RANGE_DAYS ending on `to_date`."""
    single = _parse(params.get("date"))
    if single:
        return single, single
    start = _parse(params.get("from_date"))
    end = _parse(params.get("to_date")) or timezone.localdate()
    start = start or end
    if start > end:
        start, end = end, start
    if (end - start).days >= MAX_RANGE_DAYS:
        start = end - timedelta(days=MAX_RANGE_DAYS - 1)
    return start, end


def _parse(value):
    try:
        return parse_date((value or "").strip()) if value else None
    except (TypeError, ValueError):
        return None


def has_field(model, name):
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def live(qs):
    """Rows that are not soft-deleted."""
    return qs.filter(is_deleted=False) if has_field(qs.model, "is_deleted") else qs


def scoped(qs, scope):
    model = qs.model
    if scope.company_ids is not None and has_field(model, "company_id"):
        qs = qs.filter(company_id__in=scope.company_ids)
    if scope.project_ids is not None and has_field(model, "project_id"):
        qs = qs.filter(project_id__in=scope.project_ids)
    return qs


def kg(value):
    return round(float(value or 0), 2)


def pct(part, whole):
    return round(part * 100.0 / whole, 1) if whole else 0.0


def counts_by(qs, field):
    return {
        row[field] or "": row["n"]
        for row in qs.order_by().values(field).annotate(n=Count("pk"))
    }


def per_project(qs, *, total=None):
    """{project_id: count} — or {project_id: sum(total)} when `total` is set."""
    agg = Sum(total) if total else Count("pk")
    return {
        row["project_id"] or "": (kg(row["v"]) if total else row["v"])
        for row in qs.order_by().values("project_id").annotate(v=agg)
    }


def per_company(qs, *, total=None):
    agg = Sum(total) if total else Count("pk")
    return {
        row["company_id"] or "": (kg(row["v"]) if total else row["v"])
        for row in qs.order_by().values("company_id").annotate(v=agg)
    }


def day_counts(values, scope):
    """Count aware datetimes (or dates) per local day inside the range."""
    out = Counter()
    for value in values:
        if value is None:
            continue
        day = timezone.localtime(value).date() if isinstance(value, datetime) else value
        if scope.start <= day <= scope.end:
            out[day] += 1
    return out


# ---------------------------------------------------------------- masters

# (key, label, group, model, sidebar module/screen it is maintained on).
# Models without company_id/project_id are platform-wide reference data and
# are reported with scope "global".
MASTER_CATALOG = (
    ("districts", "District", "Location Masters", District),
    ("cities", "City", "Location Masters", City),
    ("zones", "Zone", "Location Masters", Zone),
    ("wards", "Ward", "Location Masters", Ward),
    ("panchayats", "PLB (Local Body)", "Location Masters", Panchayat),
    ("block_unions", "Block Panchayat Union", "Location Masters", BlockPanchayatUnion),
    ("plants", "Plant", "Location Masters", Plant),
    ("panchayat_leaders", "PLB Leader", "Leader Management", PanchayatLeaderLogin),
    ("district_leaders", "District Leader", "Leader Management", DistrictLeaderLogin),
    ("properties", "Property", "Waste Masters", Property),
    ("subproperties", "Sub Property", "Waste Masters", SubProperty),
    ("bins", "Bin", "Waste Masters", Bins),
    ("waste_types", "Waste Type", "Waste Masters", WasteType),
    ("vehicles", "Vehicle", "Transport Masters", VehicleCreation),
    ("vehicle_types", "Vehicle Type", "Transport Masters", VehicleTypeCreation),
    ("fuels", "Fuel", "Transport Masters", Fuel),
    ("customers", "Customer", "Customer Masters", CustomerCreation),
    ("customer_app_access", "Customer App Access", "Customer Masters", CustomerAccessConfiguration),
    ("staff_templates", "Staff Template", "Schedule Setup", StaffTemplate),
    ("alternative_staff_templates", "Alternative Staff Template", "Schedule Setup", AlternativeStaffTemplate),
    ("collection_points", "Collection Point", "Schedule Setup", Collection_point),
    ("trip_plans", "Trip Plan", "Schedule Setup", TripPlan),
    ("departments", "Department", "Staff Management", Department),
    ("designations", "Designation", "Staff Management", Designation),
    ("staff", "Staff", "Staff Management", StaffcreationOfficeDetails),
    ("staff_access_configs", "Staff Access Configuration", "Staff Management", StaffAccessConfiguration),
    ("user_types", "User Type", "Role Management", UserType),
    ("staff_user_types", "Staff User Type", "Role Management", StaffUserType),
    ("contractor_user_types", "Contractor User Type", "Role Management", ContractorUserType),
    ("staff_hierarchy", "Project Staff Hierarchy", "Role Management", ProjectStaffHierarchy),
    ("complaint_categories", "Complaint Category", "Complaint Masters", ComplaintCategory),
    ("complaint_subcategories", "Complaint Subcategory", "Complaint Masters", ComplaintSubcategory),
    ("sla_rules", "SLA Rule", "Complaint Masters", ComplaintSlaRule),
)


def master_counts(scope, *, by="project"):
    """Every master's total / active / inactive count, plus a breakdown per
    project (or per company) for the masters that carry that column."""
    rows = []
    for key, label, group, model in MASTER_CATALOG:
        qs = scoped(live(model.objects.all()), scope)
        total = qs.count()
        active = qs.filter(is_active=True).count() if has_field(model, "is_active") else total
        column = f"{by}_id"
        if not has_field(model, "company_id") and not has_field(model, "project_id"):
            level = "global"
        elif has_field(model, "project_id"):
            level = "project"
        else:
            level = "company"
        breakdown = {}
        if has_field(model, column):
            breakdown = per_project(qs) if by == "project" else per_company(qs)
        rows.append({
            "key": key,
            "label": label,
            "group": group,
            "level": level,
            "total": total,
            "active": active,
            "inactive": max(total - active, 0),
            f"by_{by}": breakdown,
        })
    return rows


# ------------------------------------------------------------- operations

def _assignment_ids(scope):
    return scoped(
        DailyTripAssignment.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    ).values("unique_id")


def _plan_ids(*collection_types):
    return TripPlan.objects.filter(
        collection_type__in=collection_types, is_deleted=False,
    ).values("unique_id")


def household_waste_qs(scope):
    """Household / bulk weighments — same rule as the dashboard summary: rows
    with no trip, or on a household/bulk trip."""
    assignments = DailyTripAssignment.objects.filter(
        trip_plan_id__in=_plan_ids(
            TripPlan.COLLECTION_TYPE_HOUSEHOLD, TripPlan.COLLECTION_TYPE_BULK,
        ),
        is_deleted=False,
    ).values("unique_id")
    return scoped(
        WasteCollection.objects.filter(
            is_deleted=False,
            collection_date__gte=scope.start,
            collection_date__lte=scope.end,
        ).filter(Q(trip_assignment_id__isnull=True) | Q(trip_assignment_id__in=assignments)),
        scope,
    )


def bin_events_qs(scope):
    return scoped(
        BinCollectionEvent.objects.filter(
            is_deleted=False,
            collection_date__gte=scope.start,
            collection_date__lte=scope.end,
        ),
        scope,
    )


def operations(scope):
    """Trip, collection, exception and complaint KPIs for the range."""
    start_dt, end_dt = scope.window
    plan_types = dict(
        TripPlan.objects.filter(is_deleted=False).values_list("unique_id", "collection_type")
    )

    # ---- trips
    trips = scoped(
        DailyTripAssignment.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )
    trip_status = counts_by(trips, "status")
    trip_approval = counts_by(trips, "approval_status")
    by_type = defaultdict(lambda: {"total": 0, "completed": 0})
    durations = []
    on_time = late = 0
    for plan_id, status, scheduled, started_at, ended_at in trips.values_list(
        "trip_plan_id", "status", "scheduled_time", "actual_start_at", "actual_end_at",
    ):
        ctype = plan_types.get(plan_id) or "unplanned"
        by_type[ctype]["total"] += 1
        if status == DailyTripAssignment.STATUS_COMPLETED:
            by_type[ctype]["completed"] += 1
        if started_at and ended_at and ended_at > started_at:
            durations.append((ended_at - started_at).total_seconds() / 60)
        if started_at and scheduled:
            local_start = timezone.localtime(started_at).time()
            # 15 minutes grace, like the trip delay screen.
            limit = (datetime.combine(date.min, scheduled) + timedelta(minutes=15)).time()
            if local_start <= limit:
                on_time += 1
            else:
                late += 1
    trips_total = sum(trip_status.values())
    completed = trip_status.get(DailyTripAssignment.STATUS_COMPLETED, 0)

    # ---- trip logs
    logs = scoped(
        DailyTripLog.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )
    log_agg = logs.aggregate(
        n=Count("pk"),
        verified=Count("pk", filter=Q(log_status=DailyTripLog.LOG_STATUS_VERIFIED)),
        bin_kg=Sum("collected_weight_kg"),
        household_kg=Sum("household_collected_weight_kg"),
    )

    # ---- household stops (planned on the trips above)
    assignment_ids = _assignment_ids(scope)
    stops = DailyTripHouseholdCollection.objects.filter(
        is_deleted=False, trip_assignment_id__in=assignment_ids,
    )
    stop_status = counts_by(stops, "status")
    stops_total = sum(stop_status.values())
    stops_collected = stop_status.get(DailyTripHouseholdCollection.STATUS_COLLECTED, 0)

    # ---- collection points (bin trips)
    points = DailyTripCollectionPoint.objects.filter(
        is_deleted=False, trip_assignment_id__in=assignment_ids,
    )
    point_status = counts_by(points, "status")
    points_total = sum(point_status.values())

    # ---- weighments
    household = household_waste_qs(scope)
    household_agg = household.aggregate(
        n=Count("pk"),
        total=Sum("total_quantity"),
        wet=Sum("wet_waste"),
        dry=Sum("dry_waste"),
        mixed=Sum("mixed_waste"),
        sanitary=Sum("sanitary_waste"),
        customers=Count("customer_id", distinct=True),
    )
    bins = bin_events_qs(scope)
    bin_status = counts_by(bins, "status")
    collected_bins = bins.filter(status=BinCollectionEvent.STATUS_COLLECTED)
    bin_agg = collected_bins.aggregate(
        kg=Sum("collected_weight_kg"), distinct_bins=Count("bin_id", distinct=True),
    )
    household_kg = kg(household_agg["total"])
    bin_kg = kg(bin_agg["kg"])
    total_kg = round(household_kg + bin_kg, 2)

    waste_names = dict(WasteType.objects.values_list("unique_id", "waste_type_name"))
    waste_split = Counter()
    for label, field in (("Wet Waste", "wet"), ("Dry Waste", "dry"),
                         ("Mixed Waste", "mixed"), ("Sanitary Waste", "sanitary")):
        waste_split[label] += kg(household_agg[field])
    classified = sum(waste_split.values())
    if household_kg > classified:
        waste_split["Unclassified"] += round(household_kg - classified, 2)
    for row in collected_bins.order_by().values("waste_type_id").annotate(v=Sum("collected_weight_kg")):
        waste_split[waste_names.get(row["waste_type_id"]) or "Unclassified"] += kg(row["v"])

    # ---- exceptions
    breakdowns = scoped(
        VehicleBreakdown.objects.filter(
            is_deleted=False, created_at__gte=start_dt, created_at__lt=end_dt,
        ),
        scope,
    )
    retrips = scoped(
        TripRetripRequest.objects.filter(
            is_deleted=False, created_at__gte=start_dt, created_at__lt=end_dt,
        ),
        scope,
    )
    delays = scoped(
        TripDelayReport.objects.filter(
            is_deleted=False, created_at__gte=start_dt, created_at__lt=end_dt,
        ),
        scope,
    )
    delay_minutes = delays.aggregate(v=Sum("estimated_delay_minutes"))["v"] or 0
    delay_count = delays.count()

    # ---- complaints
    tickets = complaint_tickets(scope)

    # ---- attendance
    attendance = attendance_summary(scope)

    days = max(len(scope.days), 1)
    return {
        "trips": {
            "total": trips_total,
            "completed": completed,
            "in_progress": trip_status.get(DailyTripAssignment.STATUS_IN_PROGRESS, 0),
            "scheduled": trip_status.get(DailyTripAssignment.STATUS_SCHEDULED, 0),
            "cancelled": trip_status.get(DailyTripAssignment.STATUS_CANCELLED, 0),
            "completion_rate": pct(completed, trips_total),
            "approval": trip_approval,
            "by_collection_type": dict(by_type),
            "vehicles_used": trips.exclude(vehicle_id__isnull=True).values("vehicle_id").distinct().count(),
            "teams_used": trips.exclude(staff_template_id__isnull=True).values("staff_template_id").distinct().count(),
            "avg_duration_min": round(sum(durations) / len(durations), 1) if durations else 0,
            "on_time": on_time,
            "late_start": late,
            "on_time_rate": pct(on_time, on_time + late),
            "per_day": round(trips_total / days, 1),
        },
        "trip_logs": {
            "total": log_agg["n"] or 0,
            "verified": log_agg["verified"] or 0,
            "unverified": max((log_agg["n"] or 0) - (log_agg["verified"] or 0), 0),
            "verification_rate": pct(log_agg["verified"] or 0, log_agg["n"] or 0),
            "bin_kg": kg(log_agg["bin_kg"]),
            "household_kg": kg(log_agg["household_kg"]),
            "total_kg": round(kg(log_agg["bin_kg"]) + kg(log_agg["household_kg"]), 2),
        },
        "waste": {
            "total_kg": total_kg,
            "total_tons": round(total_kg / 1000, 2),
            "household_kg": household_kg,
            "bin_kg": bin_kg,
            "avg_kg_per_day": round(total_kg / days, 2),
            "avg_kg_per_trip": round(total_kg / completed, 2) if completed else 0,
            "by_waste_type": [
                {"name": name, "kg": round(value, 2), "share": pct(value, total_kg)}
                for name, value in waste_split.most_common()
                if value > 0
            ],
        },
        "households": {
            "weighments": household_agg["n"] or 0,
            "customers_served": household_agg["customers"] or 0,
            "planned_stops": stops_total,
            "collected": stops_collected,
            "status": stop_status,
            "coverage_rate": pct(stops_collected, stops_total),
        },
        "bins": {
            "events": sum(bin_status.values()),
            "collected": bin_status.get(BinCollectionEvent.STATUS_COLLECTED, 0),
            "distinct_bins_collected": bin_agg["distinct_bins"] or 0,
            "status": bin_status,
        },
        "collection_points": {
            "planned": points_total,
            "status": point_status,
            "collected": point_status.get(DailyTripCollectionPoint.STATUS_COLLECTED, 0),
            "coverage_rate": pct(point_status.get(DailyTripCollectionPoint.STATUS_COLLECTED, 0), points_total),
        },
        "exceptions": {
            "breakdowns": breakdowns.count(),
            "breakdown_status": counts_by(breakdowns, "status"),
            "breakdown_reasons": counts_by(breakdowns, "breakdown_reason"),
            "retrips": retrips.count(),
            "retrip_status": counts_by(retrips, "status"),
            "delays": delay_count,
            "delay_status": counts_by(delays, "status"),
            "delay_reasons": counts_by(delays, "delay_reason"),
            "avg_delay_min": round(delay_minutes / delay_count, 1) if delay_count else 0,
        },
        "complaints": tickets,
        "attendance": attendance,
    }


def complaint_tickets(scope):
    start_dt, end_dt = scope.window
    final_ids = set(
        ComplaintStatus.objects.filter(is_final=True).values_list("unique_id", flat=True)
    )
    status_names = dict(ComplaintStatus.objects.values_list("unique_id", "status_name"))
    all_tickets = scoped(live(ComplaintTicket.objects.all()), scope)
    raised = all_tickets.filter(created__gte=start_dt, created__lt=end_dt)
    open_now = all_tickets.exclude(status_id__in=final_ids)
    now = timezone.now()
    return {
        "raised": raised.count(),
        "resolved": all_tickets.filter(resolved_at__gte=start_dt, resolved_at__lt=end_dt).count(),
        "closed": all_tickets.filter(closed_at__gte=start_dt, closed_at__lt=end_dt).count(),
        "open": open_now.count(),
        "escalated_open": open_now.filter(is_escalated=True).count(),
        "overdue_open": open_now.filter(next_escalation_due_at__lt=now).count(),
        "reopened": raised.filter(reopened_count__gt=0).count(),
        "by_status": {
            status_names.get(key, key or "Unknown"): value
            for key, value in counts_by(raised, "status_id").items()
        },
    }


def attendance_summary(scope):
    """Distinct staff punched IN per day (face recognition + new punch log)."""
    staff = scoped(
        StaffcreationOfficeDetails.objects.filter(is_deleted=False, active_status=True),
        scope,
    )
    staff_ids = staff.values("staff_unique_id")
    present = defaultdict(set)
    for staff_id, day in Recognized.objects.filter(
        staff_id__in=staff_ids, punch_type="IN",
        recognition_date__gte=scope.start, recognition_date__lte=scope.end,
    ).values_list("staff_id", "recognition_date"):
        present[day].add(staff_id)
    for staff_id, day in AttendanceNew.objects.filter(
        is_deleted=False, staff_id__in=staff_ids, log_type="IN",
        punch_date__gte=scope.start, punch_date__lte=scope.end,
    ).values_list("staff_id", "punch_date"):
        present[day].add(staff_id)
    total = staff.count()
    per_day = {day: len(ids) for day, ids in present.items()}
    days = max(len(scope.days), 1)
    avg = round(sum(per_day.values()) / days, 1)
    return {
        "staff": total,
        "avg_present": avg,
        "attendance_rate": pct(avg, total),
        "present_last_day": per_day.get(scope.end, 0),
        "per_day": per_day,
    }


# ------------------------------------------------------------------ daily

def daily_series(scope):
    """One row per day of the range: trips, weights, stops, exceptions."""
    rows = {
        day: {
            "date": day.isoformat(),
            "trips": 0, "trips_completed": 0, "trip_logs": 0,
            "household_kg": 0.0, "bin_kg": 0.0, "total_kg": 0.0,
            "households_collected": 0, "bins_collected": 0,
            "breakdowns": 0, "complaints": 0, "present": 0,
        }
        for day in scope.days
    }

    trips = scoped(
        DailyTripAssignment.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )
    for row in trips.order_by().values("trip_date").annotate(
        n=Count("pk"),
        done=Count("pk", filter=Q(status=DailyTripAssignment.STATUS_COMPLETED)),
    ):
        if row["trip_date"] in rows:
            rows[row["trip_date"]]["trips"] = row["n"]
            rows[row["trip_date"]]["trips_completed"] = row["done"]

    logs = scoped(
        DailyTripLog.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )
    for row in logs.order_by().values("trip_date").annotate(n=Count("pk")):
        if row["trip_date"] in rows:
            rows[row["trip_date"]]["trip_logs"] = row["n"]

    for row in household_waste_qs(scope).order_by().values("collection_date").annotate(
        v=Sum("total_quantity"), n=Count("customer_id", distinct=True),
    ):
        if row["collection_date"] in rows:
            rows[row["collection_date"]]["household_kg"] = kg(row["v"])
            rows[row["collection_date"]]["households_collected"] = row["n"]

    collected = bin_events_qs(scope).filter(status=BinCollectionEvent.STATUS_COLLECTED)
    for row in collected.order_by().values("collection_date").annotate(
        v=Sum("collected_weight_kg"), n=Count("bin_id", distinct=True),
    ):
        if row["collection_date"] in rows:
            rows[row["collection_date"]]["bin_kg"] = kg(row["v"])
            rows[row["collection_date"]]["bins_collected"] = row["n"]

    start_dt, end_dt = scope.window
    breakdown_days = day_counts(
        scoped(
            VehicleBreakdown.objects.filter(
                is_deleted=False, created_at__gte=start_dt, created_at__lt=end_dt,
            ),
            scope,
        ).values_list("created_at", flat=True),
        scope,
    )
    ticket_days = day_counts(
        scoped(
            live(ComplaintTicket.objects.filter(created__gte=start_dt, created__lt=end_dt)),
            scope,
        ).values_list("created", flat=True),
        scope,
    )
    present = attendance_summary(scope)["per_day"]
    for day, row in rows.items():
        row["total_kg"] = round(row["household_kg"] + row["bin_kg"], 2)
        row["breakdowns"] = breakdown_days.get(day, 0)
        row["complaints"] = ticket_days.get(day, 0)
        row["present"] = present.get(day, 0)
    return list(rows.values())


# ---------------------------------------------------------------- leaders

def top_performers(scope, limit=10):
    """Top vehicles, drivers, PLBs and wards by collected weight."""
    logs = scoped(
        DailyTripLog.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )

    def ranked(field):
        totals = defaultdict(lambda: {"trips": 0, "kg": Decimal("0")})
        for key, bin_kg, household_kg in logs.exclude(**{f"{field}__isnull": True}).values_list(
            field, "collected_weight_kg", "household_collected_weight_kg",
        ):
            totals[key]["trips"] += 1
            totals[key]["kg"] += (bin_kg or 0) + (household_kg or 0)
        return sorted(totals.items(), key=lambda item: item[1]["kg"], reverse=True)[:limit]

    vehicles = ranked("vehicle_id")
    vehicle_names = dict(
        VehicleCreation.objects.filter(unique_id__in=[k for k, _ in vehicles])
        .values_list("unique_id", "vehicle_no")
    )
    drivers = ranked("driver_id")
    driver_names = dict(
        StaffcreationOfficeDetails.objects.filter(staff_unique_id__in=[k for k, _ in drivers])
        .values_list("staff_unique_id", "employee_name")
    )

    plbs = (
        bin_events_qs(scope).filter(status=BinCollectionEvent.STATUS_COLLECTED)
        .exclude(panchayat_id__isnull=True)
        .order_by().values("panchayat_id")
        .annotate(v=Sum("collected_weight_kg"), n=Count("pk"))
        .order_by("-v")[:limit]
    )
    plb_names = dict(
        Panchayat.objects.filter(unique_id__in=[r["panchayat_id"] for r in plbs])
        .values_list("unique_id", "panchayat_name")
    )
    wards = (
        household_waste_qs(scope).exclude(ward_id__isnull=True)
        .order_by().values("ward_id")
        .annotate(v=Sum("total_quantity"), n=Count("pk"))
        .order_by("-v")[:limit]
    )
    ward_names = dict(
        Ward.objects.filter(unique_id__in=[r["ward_id"] for r in wards])
        .values_list("unique_id", "ward_name")
    )
    return {
        "vehicles": [
            {"id": key, "name": vehicle_names.get(key, key), "trips": v["trips"], "kg": kg(v["kg"])}
            for key, v in vehicles
        ],
        "drivers": [
            {"id": key, "name": driver_names.get(key, key), "trips": v["trips"], "kg": kg(v["kg"])}
            for key, v in drivers
        ],
        "plbs": [
            {"id": r["panchayat_id"], "name": plb_names.get(r["panchayat_id"], r["panchayat_id"]),
             "collections": r["n"], "kg": kg(r["v"])}
            for r in plbs
        ],
        "wards": [
            {"id": r["ward_id"], "name": ward_names.get(r["ward_id"], r["ward_id"]),
             "collections": r["n"], "kg": kg(r["v"])}
            for r in wards
        ],
    }


# ----------------------------------------------------------- per project

def project_breakdown(scope, projects):
    """Operations + headcount per project, for the project comparison table."""
    trips = scoped(
        DailyTripAssignment.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )
    trip_rows = {
        r["project_id"]: r
        for r in trips.order_by().values("project_id").annotate(
            n=Count("pk"),
            done=Count("pk", filter=Q(status=DailyTripAssignment.STATUS_COMPLETED)),
        )
    }
    household_kg = per_project(household_waste_qs(scope), total="total_quantity")
    collected_bins = bin_events_qs(scope).filter(status=BinCollectionEvent.STATUS_COLLECTED)
    bin_kg = per_project(collected_bins, total="collected_weight_kg")
    bins_collected = per_project(collected_bins)
    logs = per_project(scoped(
        DailyTripLog.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    ))
    start_dt, end_dt = scope.window
    breakdowns = per_project(scoped(
        VehicleBreakdown.objects.filter(
            is_deleted=False, created_at__gte=start_dt, created_at__lt=end_dt,
        ),
        scope,
    ))
    final_ids = ComplaintStatus.objects.filter(is_final=True).values("unique_id")
    open_tickets = per_project(
        scoped(live(ComplaintTicket.objects.exclude(status_id__in=final_ids)), scope)
    )
    staff = per_project(scoped(live(StaffcreationOfficeDetails.objects.all()), scope))
    vehicles = per_project(scoped(live(VehicleCreation.objects.all()), scope))
    customers = per_project(scoped(live(CustomerCreation.objects.all()), scope))
    bins = per_project(scoped(live(Bins.objects.all()), scope))

    # Rows with no project (e.g. app weighments saved without tenancy) get a
    # row of their own when the caller sees every project, so the table adds
    # up to the headline totals.
    unlinked = None
    if scope.project_ids is None:
        unlinked = SimpleNamespace(unique_id=None, name="Not linked to a project", company_id=None)
        trip_rows[None] = trip_rows.get(None) or trip_rows.get("") or {}

    out = []
    for project in [*projects, unlinked]:
        if project is None:
            continue
        pid = project.unique_id
        trip = trip_rows.get(pid, {})
        if pid is None:
            pid = ""
        total = round(household_kg.get(pid, 0) + bin_kg.get(pid, 0), 2)
        row = {
            "project_id": pid,
            "project_name": project.name,
            "company_id": project.company_id,
            "trips": trip.get("n", 0),
            "trips_completed": trip.get("done", 0),
            "completion_rate": pct(trip.get("done", 0), trip.get("n", 0)),
            "trip_logs": logs.get(pid, 0),
            "household_kg": household_kg.get(pid, 0),
            "bin_kg": bin_kg.get(pid, 0),
            "total_kg": total,
            "bins_collected": bins_collected.get(pid, 0),
            "breakdowns": breakdowns.get(pid, 0),
            "open_complaints": open_tickets.get(pid, 0),
            "staff": staff.get(pid, 0),
            "vehicles": vehicles.get(pid, 0),
            "customers": customers.get(pid, 0),
            "bins": bins.get(pid, 0),
        }
        if project is unlinked:
            if not any(row[k] for k in ("trips", "trip_logs", "total_kg", "bins_collected",
                                        "breakdowns", "open_complaints", "staff", "vehicles",
                                        "customers", "bins")):
                continue
            row["project_id"] = ""
        out.append(row)
    return out


def fleet_health(scope):
    """Vehicle master health: active, idle on the last day, insurance due."""
    vehicles = scoped(live(VehicleCreation.objects.all()), scope)
    today = timezone.localdate()
    used_last_day = set(
        scoped(
            DailyTripAssignment.objects.filter(is_deleted=False, trip_date=scope.end),
            scope,
        ).exclude(vehicle_id__isnull=True).values_list("vehicle_id", flat=True)
    )
    active_ids = set(vehicles.filter(is_active=True).values_list("unique_id", flat=True))
    insurance = vehicles.exclude(insurance_expiry_date__isnull=True)
    return {
        "total": vehicles.count(),
        "active": len(active_ids),
        "on_trip_last_day": len(active_ids & used_last_day),
        "idle_last_day": len(active_ids - used_last_day),
        "insurance_expired": insurance.filter(insurance_expiry_date__lt=today).count(),
        "insurance_due_30d": insurance.filter(
            insurance_expiry_date__gte=today,
            insurance_expiry_date__lte=today + timedelta(days=30),
        ).count(),
        "open_breakdowns": scoped(
            VehicleBreakdown.objects.filter(
                is_deleted=False, status=VehicleBreakdown.STATUS_REPORTED,
            ),
            scope,
        ).count(),
    }


def staff_summary(scope):
    staff = scoped(live(StaffcreationOfficeDetails.objects.all()), scope)
    agg = staff.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True, active_status=True)),
        login_enabled=Count("pk", filter=Q(login_enabled=True)),
        approved=Count("pk", filter=Q(approval_status=StaffcreationOfficeDetails.APPROVAL_APPROVED)),
        pending=Count("pk", filter=Q(approval_status=StaffcreationOfficeDetails.APPROVAL_PENDING)),
    )
    role_names = dict(StaffUserType.objects.values_list("unique_id", "name"))
    contractor_names = dict(ContractorUserType.objects.values_list("unique_id", "name"))
    roles = Counter()
    for staff_role, contractor_role in staff.values_list("staffusertype_id", "contractorusertype_id"):
        name = role_names.get(staff_role) or contractor_names.get(contractor_role) or "Unassigned"
        roles[pretty_name(name)] += 1
    return {**{k: v or 0 for k, v in agg.items()}, "by_role": dict(roles.most_common())}


def pretty_name(name):
    return str(name).replace("_", " ").title() if name else "Unassigned"
