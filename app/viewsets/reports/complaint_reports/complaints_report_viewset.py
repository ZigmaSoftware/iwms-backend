"""Complaints report: intake, resolution, pendency and SLA analytics over
ComplaintTicket for one received-date range.

Every aggregate is computed from the same filtered ticket set (tenant scope +
date range + zone/ward/category/source), so the KPIs, charts, ward table and
register always agree with each other. The register's status tab and search
only narrow the register rows, never the aggregates above them.

The ticket's master references (status/category/source/zone/ward/staff) are
plain CharFields holding the master's unique_id, so names are resolved with
one lookup per master rather than ORM joins.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from rest_framework.response import Response

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintSource,
    ComplaintStatus,
    ComplaintTicket,
)
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.serializers.core_modules.complaint_management.ticket_serializers import (
    ComplaintTicketSerializer,
)
from app.services.complaint_ticket_routing import CLOSED_STATUS_CODES
from app.viewsets.reports.waste_reports.daily_waste_comparison_viewset import _comma_values
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet

# CLOSED_STATUS_CODES also covers REJECTED/CANCELLED; those are closed but
# not "resolved", so they get their own bucket and stay out of SLA figures.
RESOLVED_STATUS_CODES = ("RESOLVED", "CLOSED")
STATUS_BUCKETS = ("open", "in_progress", "escalated", "resolved")
DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
AGE_BUCKETS = (
    ("0_24", "0 – 24 h", 0, 24),
    ("24_48", "24 – 48 h", 24, 48),
    ("48_72", "48 – 72 h", 48, 72),
    ("72_plus", "Over 72 h", 72, None),
)
TICKET_FIELDS = (
    "unique_id",
    "ticket_no",
    "created",
    "category_id",
    "source_id",
    "status_id",
    "zone_id",
    "ward_id",
    "assigned_staff_id",
    "is_escalated",
    "next_escalation_due_at",
    "resolved_at",
    "closed_at",
)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _start_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _positive_int(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _percent(part, whole):
    return round(part * 100 / whole, 1) if whole else 0.0


def _status_bucket(status_code, is_escalated):
    if status_code in RESOLVED_STATUS_CODES:
        return "resolved"
    if status_code in CLOSED_STATUS_CODES:
        return "rejected"
    if is_escalated or status_code == "ESCALATED":
        return "escalated"
    if status_code == "IN_PROGRESS":
        return "in_progress"
    return "open"


def _finished_at(row):
    return row["resolved_at"] or row["closed_at"]


def _is_breached(row, bucket, now):
    """A ticket breaches SLA once it has escalated, or once its current
    resolution deadline passed before it was resolved."""
    if row["is_escalated"]:
        return True
    due = row["next_escalation_due_at"]
    if due is None:
        return False
    if bucket == "resolved":
        finished = _finished_at(row)
        return bool(finished and finished > due)
    return now > due


def _name_map(model, key_field, name_field, ids):
    ids = {value for value in ids if value}
    if not ids:
        return {}
    return dict(
        model.objects.filter(**{f"{key_field}__in": ids}).values_list(key_field, name_field)
    )


class ComplaintsReportViewSet(CompanyScopedViewSet):
    permission_resource = "ComplaintsReport"
    queryset = ComplaintTicket.objects.filter(is_deleted=False)
    serializer_class = ComplaintTicketSerializer
    lookup_field = "unique_id"
    http_method_names = ["get", "head", "options"]

    def _date_range(self, params):
        today = timezone.localdate()
        to_date = _parse_date(params.get("to_date")) or today
        from_date = _parse_date(params.get("from_date")) or (
            to_date - timedelta(days=DEFAULT_RANGE_DAYS - 1)
        )
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        if (to_date - from_date).days >= MAX_RANGE_DAYS:
            from_date = to_date - timedelta(days=MAX_RANGE_DAYS - 1)
        return from_date, to_date

    def list(self, request):
        params = request.query_params
        now = timezone.now()
        from_date, to_date = self._date_range(params)

        # Tenant scoping only — the generic list-filter backends would treat
        # report params like from_date/status as literal model fields.
        scoped = self._scope_to_tenant(ComplaintTicket.objects.filter(is_deleted=False))
        option_rows = list(scoped.values("category_id", "source_id").distinct())

        # Aware day bounds instead of `created__date__*`: on MySQL without
        # loaded timezone tables CONVERT_TZ yields NULL and matches nothing.
        queryset = scoped.filter(
            created__gte=_start_of_day(from_date),
            created__lt=_start_of_day(to_date + timedelta(days=1)),
        )
        for param, field in (
            ("zone_id", "zone_id"),
            ("ward_id", "ward_id"),
            ("category_id", "category_id"),
            ("source_id", "source_id"),
        ):
            values = _comma_values(params.get(param))
            if values:
                queryset = queryset.filter(**{f"{field}__in": values})

        rows = list(queryset.order_by("-created").values(*TICKET_FIELDS))

        statuses = {
            unique_id: (code, name)
            for unique_id, code, name in ComplaintStatus.objects.filter(
                unique_id__in={r["status_id"] for r in rows if r["status_id"]}
            ).values_list("unique_id", "status_code", "status_name")
        }
        categories = _name_map(
            ComplaintCategory,
            "unique_id",
            "category_name",
            [r["category_id"] for r in rows] + [r["category_id"] for r in option_rows],
        )
        sources = _name_map(
            ComplaintSource,
            "unique_id",
            "source_name",
            [r["source_id"] for r in rows] + [r["source_id"] for r in option_rows],
        )
        zones = _name_map(Zone, "unique_id", "zone_name", [r["zone_id"] for r in rows])
        wards = _name_map(Ward, "unique_id", "ward_name", [r["ward_id"] for r in rows])
        staff = _name_map(
            StaffcreationOfficeDetails,
            "staff_unique_id",
            "employee_name",
            [r["assigned_staff_id"] for r in rows],
        )

        bucket_counts = defaultdict(int)
        received_by_day = defaultdict(int)
        resolved_by_day = defaultdict(int)
        category_counts = defaultdict(int)
        age_counts = defaultdict(int)
        ward_stats = defaultdict(lambda: {"received": 0, "resolved": 0, "pending": 0, "sla_total": 0, "sla_met": 0})
        sla_total = sla_met = 0
        resolution_hours = []

        for row in rows:
            status_code, status_name = statuses.get(row["status_id"], ("", ""))
            bucket = _status_bucket(status_code, row["is_escalated"])
            breached = _is_breached(row, bucket, now)
            finished = _finished_at(row) if bucket == "resolved" else None

            row["_bucket"] = bucket
            row["_status_code"] = status_code
            row["_status_name"] = status_name
            row["_breached"] = breached
            row["_resolution_hours"] = (
                round((finished - row["created"]).total_seconds() / 3600, 1) if finished else None
            )

            bucket_counts[bucket] += 1
            received_by_day[timezone.localtime(row["created"]).date()] += 1
            category_counts[row["category_id"]] += 1

            ward = ward_stats[(row["ward_id"], row["zone_id"])]
            ward["received"] += 1

            if bucket == "resolved":
                ward["resolved"] += 1
                if finished:
                    resolved_by_day[timezone.localtime(finished).date()] += 1
                    resolution_hours.append(row["_resolution_hours"])
            elif bucket != "rejected":
                ward["pending"] += 1
                age_hours = (now - row["created"]).total_seconds() / 3600
                for key, _label, low, high in AGE_BUCKETS:
                    if age_hours >= low and (high is None or age_hours < high):
                        age_counts[key] += 1
                        break

            if bucket != "rejected":
                sla_total += 1
                ward["sla_total"] += 1
                if not breached:
                    sla_met += 1
                    ward["sla_met"] += 1

        total = len(rows)
        pending_total = sum(age_counts.values())

        daily_trend = []
        day = from_date
        while day <= to_date:
            daily_trend.append({
                "date": day.isoformat(),
                "received": received_by_day.get(day, 0),
                "resolved": resolved_by_day.get(day, 0),
            })
            day += timedelta(days=1)

        category_breakdown = sorted(
            (
                {
                    "category_id": category_id or "",
                    "category_name": categories.get(category_id) or "Uncategorised",
                    "count": count,
                    "share_percent": _percent(count, total),
                }
                for category_id, count in category_counts.items()
            ),
            key=lambda item: -item["count"],
        )

        ward_breakdown = sorted(
            (
                {
                    "ward_id": ward_id or "",
                    "ward_name": wards.get(ward_id) or "No ward",
                    "zone_id": zone_id or "",
                    "zone_name": zones.get(zone_id) or "",
                    "received": stats["received"],
                    "resolved": stats["resolved"],
                    "pending": stats["pending"],
                    "sla_compliance_percent": _percent(stats["sla_met"], stats["sla_total"]),
                }
                for (ward_id, zone_id), stats in ward_stats.items()
            ),
            key=lambda item: (-item["pending"], -item["received"]),
        )

        # Register: status tab + search narrow the rows, not the aggregates.
        register = rows
        status_filter = (params.get("status") or "").strip().lower()
        if status_filter in STATUS_BUCKETS:
            register = [r for r in register if r["_bucket"] == status_filter]
        search = (params.get("search") or "").strip().lower()
        if search:
            register = [r for r in register if search in (r["ticket_no"] or "").lower()]

        count = len(register)
        if params.get("export") in ("1", "true", "True"):
            page_rows = register
        else:
            limit = min(_positive_int(params.get("limit"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
            page = _positive_int(params.get("page"), 1)
            page_rows = register[(page - 1) * limit: page * limit]

        results = [
            {
                "unique_id": r["unique_id"],
                "ticket_no": r["ticket_no"],
                "created": r["created"],
                "category_name": categories.get(r["category_id"]) or "",
                "zone_name": zones.get(r["zone_id"]) or "",
                "ward_name": wards.get(r["ward_id"]) or "",
                "source_name": sources.get(r["source_id"]) or "",
                "assigned_staff_name": staff.get(r["assigned_staff_id"]) or "",
                "status_code": r["_status_code"],
                "status_name": r["_status_name"],
                "status_bucket": r["_bucket"],
                "sla_due_at": r["next_escalation_due_at"],
                "resolved_at": _finished_at(r) if r["_bucket"] == "resolved" else None,
                "resolution_hours": r["_resolution_hours"],
                "is_breached": r["_breached"],
            }
            for r in page_rows
        ]

        return Response({
            "period": {"from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
            "kpis": {
                "total": total,
                "open": bucket_counts["open"],
                "in_progress": bucket_counts["in_progress"],
                "escalated": bucket_counts["escalated"],
                "resolved": bucket_counts["resolved"],
                "rejected": bucket_counts["rejected"],
                "pending": pending_total,
                "resolved_percent": _percent(bucket_counts["resolved"], total),
                "sla_compliance_percent": _percent(sla_met, sla_total),
                "avg_resolution_hours": (
                    round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
                ),
                "zone_count": len({r["zone_id"] for r in rows if r["zone_id"]}),
                "ward_count": len({r["ward_id"] for r in rows if r["ward_id"]}),
            },
            "status_counts": {
                "all": total,
                **{bucket: bucket_counts[bucket] for bucket in STATUS_BUCKETS},
            },
            "daily_trend": daily_trend,
            "category_breakdown": category_breakdown,
            "pending_aging": [
                {"key": key, "label": label, "count": age_counts[key]}
                for key, label, _low, _high in AGE_BUCKETS
            ],
            "ward_breakdown": ward_breakdown,
            "filter_options": {
                "categories": sorted(
                    (
                        {"value": cid, "label": categories[cid]}
                        for cid in {r["category_id"] for r in option_rows}
                        if cid in categories
                    ),
                    key=lambda item: item["label"].lower(),
                ),
                "sources": sorted(
                    (
                        {"value": sid, "label": sources[sid]}
                        for sid in {r["source_id"] for r in option_rows}
                        if sid in sources
                    ),
                    key=lambda item: item["label"].lower(),
                ),
            },
            "results": results,
            "count": count,
        })
