"""
Audit Dashboard: one summary per audit trail (Common, Login, User Access,
Static Route, Complaint) over a recent window — headline counts, a per-day
trend, a breakdown for the doughnut, and the matching rows flattened to the
same shape the dashboard table renders.

Every trail is read from its own table; nothing is copied or cached. The
viewset hands in a queryset already confined to the caller's tenancy.

Days are bucketed in Python on local time rather than with TruncDate, so
the trend does not depend on MySQL having its timezone tables loaded.
"""
from collections import Counter
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.utils import timezone

from app.models.core_modules.complaint_management import ComplaintStatus, ComplaintTicket
from app.models.core_modules.complaint_management.transactions import ComplaintEscalationHistory
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.audits.loginAudit import LoginAudit
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.project import Project
from app.services.complaint_audit import summarize_tickets
from app.utils.common_audit import CommonAudit

ALLOWED_DAYS = (7, 30, 90)
DEFAULT_DAYS = 30


def _name_map(model, key_field, name_field, ids):
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(model.objects.filter(**{f"{key_field}__in": ids}).values_list(key_field, name_field))


def _account_names(ids):
    """An Account id is a staff_unique_id or a User.unique_id."""
    return {
        **_name_map(get_user_model(), "unique_id", "username", ids),
        **_name_map(Staffcreation, "staff_unique_id", "employee_name", ids),
    }


def _iso(value):
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# One class per trail. Each names its table's columns and turns rows into
# KPIs, breakdown slices and table rows.
# ---------------------------------------------------------------------------


class _Trail:
    model = None
    date_field = None
    company_field = "company_id"
    project_field = "project_id"
    search_fields = ()

    def base_queryset(self):
        return self.model.objects.all()

    def search(self, queryset, term):
        query = Q()
        for field in self.search_fields:
            query |= Q(**{f"{field}__icontains": term})
        return queryset.filter(query)

    def ordered(self, queryset):
        return queryset.order_by(f"-{self.date_field}", "-pk")

    def kpis(self, queryset):
        raise NotImplementedError

    def breakdown(self, queryset):
        raise NotImplementedError

    def rows(self, records):
        raise NotImplementedError

    @staticmethod
    def _slices(counts, labels=None):
        labels = labels or {}
        return [
            {"key": key, "label": labels.get(key, key), "count": count}
            for key, count in sorted(counts.items(), key=lambda kv: -kv[1])
            if key is not None
        ]


class CommonTrail(_Trail):
    model = CommonAudit
    date_field = "createdAt"
    company_field = "company_unique_id"
    project_field = "project_unique_id"
    search_fields = ("module_name", "endpoint_name", "createdBy", "created_by_name", "object_id")

    # Writes are recorded by HTTP method; UPLOAD/DOWNLOAD are the manual
    # Excel events, which change no record.
    ACTIONS = {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}

    def _action(self, method):
        return self.ACTIONS.get((method or "").upper(), "OTHER")

    def kpis(self, queryset):
        methods = Counter(self._action(m) for m in queryset.values_list("method", flat=True))
        return {
            "total": sum(methods.values()),
            "updates": methods["UPDATE"],
            "deletions": methods["DELETE"],
            "active_users": queryset.exclude(createdBy__isnull=True).values("createdBy").distinct().count(),
        }

    def breakdown(self, queryset):
        return self._slices(Counter(self._action(m) for m in queryset.values_list("method", flat=True)))

    def rows(self, records):
        return [
            {
                "id": r.uuid,
                "date": _iso(r.createdAt),
                "user": r.created_by_name or r.createdBy,
                "module": r.module_name,
                "action": self._action(r.method),
                "record": r.object_id,
                "project": r.project_name,
                "success": r.success,
            }
            for r in records
        ]


class LoginTrail(_Trail):
    model = LoginAudit
    date_field = "timestamp"
    search_fields = ("username", "ip_address", "reason")

    @staticmethod
    def device(user_agent):
        ua = (user_agent or "").lower()
        if not ua:
            return "Unknown"
        if "android" in ua or "okhttp" in ua:
            return "Android"
        if any(token in ua for token in ("iphone", "ipad", "ios", "darwin")):
            return "iOS"
        if "dart" in ua:
            return "Mobile app"
        return "Web"

    def kpis(self, queryset):
        total = queryset.count()
        succeeded = queryset.filter(success=True).count()
        return {
            "total": total,
            "success_rate": round(succeeded / total * 100) if total else None,
            "failed": total - succeeded,
            "unique_users": queryset.filter(success=True).values("username").distinct().count(),
        }

    def breakdown(self, queryset):
        counts = Counter(
            "SUCCESS" if ok else "FAILED" for ok in queryset.values_list("success", flat=True)
        )
        return self._slices(counts)

    def rows(self, records):
        projects = _name_map(Project, "unique_id", "name", {r.project_id for r in records})
        return [
            {
                "id": r.unique_id,
                "date": _iso(r.timestamp),
                "user": r.username,
                "device": self.device(r.user_agent),
                "ip": r.ip_address,
                "status": "SUCCESS" if r.success else "FAILED",
                "reason": r.reason,
                "project": projects.get(r.project_id),
            }
            for r in records
        ]


class AccessTrail(_Trail):
    model = PermissionAuditLog
    date_field = "timestamp"
    search_fields = ("updated_by", "target_id", "source", "action_type")

    SOURCE_LABELS = dict(PermissionAuditLog.SOURCE_CHOICES)

    def kpis(self, queryset):
        actions = Counter(queryset.values_list("action_type", flat=True))
        return {
            "total": sum(actions.values()),
            "created": actions["CREATED"],
            "updated": actions["UPDATED"],
            "deleted": actions["DELETED"],
        }

    def breakdown(self, queryset):
        return self._slices(Counter(queryset.values_list("source", flat=True)), self.SOURCE_LABELS)

    def rows(self, records):
        actors = _account_names({r.updated_by for r in records})
        targets = {
            **_name_map(CustomerCreation, "unique_id", "customer_name", {r.target_id for r in records}),
            **_name_map(Staffcreation, "staff_unique_id", "employee_name", {r.target_id for r in records}),
        }
        projects = _name_map(Project, "unique_id", "name", {r.project_id for r in records})
        return [
            {
                "id": r.pk,
                "date": _iso(r.timestamp),
                "user": actors.get(r.updated_by) or r.updated_by,
                # Company-level grants have no single recipient.
                "target": targets.get(r.target_id) or r.target_id,
                "source": r.source,
                "source_label": self.SOURCE_LABELS.get(r.source, r.source),
                "change": r.action_type,
                "project": projects.get(r.project_id),
            }
            for r in records
        ]


class RouteTrail(_Trail):
    model = StaticRouteAuditLog
    date_field = "timestamp"
    search_fields = ("trip_plan_code", "trip_plan_id", "updated_by")

    CHANGE_LABELS = dict(StaticRouteAuditLog.CHANGE_TYPE_CHOICES)
    TRIGGER_LABELS = dict(StaticRouteAuditLog.TRIGGER_CHOICES)
    DETOUR_CHANGES = (
        StaticRouteAuditLog.CHANGE_DETOUR_ADDED,
        StaticRouteAuditLog.CHANGE_DETOUR_MOVED,
        StaticRouteAuditLog.CHANGE_DETOUR_REMOVED,
    )

    def kpis(self, queryset):
        return {
            "total": queryset.count(),
            "detour_changes": queryset.filter(change_type__in=self.DETOUR_CHANGES).count(),
            "trips_rerouted": queryset.aggregate(n=Sum("affected_trip_count"))["n"] or 0,
            "routing_errors": queryset.exclude(routing_error__isnull=True).exclude(routing_error="").count(),
        }

    def breakdown(self, queryset):
        return self._slices(Counter(queryset.values_list("change_type", flat=True)), self.CHANGE_LABELS)

    def rows(self, records):
        actors = _account_names({r.updated_by for r in records})
        projects = _name_map(Project, "unique_id", "name", {r.project_id for r in records})
        return [
            {
                "id": r.pk,
                "date": _iso(r.timestamp),
                "trip_plan": r.trip_plan_code or r.trip_plan_id,
                "change": r.change_type,
                "change_label": self.CHANGE_LABELS.get(r.change_type, r.change_type),
                "trigger_label": self.TRIGGER_LABELS.get(r.trigger, r.trigger),
                "distance_change_km": round((r.distance_change_meters or 0) / 1000, 2),
                "affected_trips": r.affected_trip_count,
                "user": actors.get(r.updated_by) or r.updated_by,
                "project": projects.get(r.project_id),
            }
            for r in records
        ]


class ComplaintTrail(_Trail):
    model = ComplaintTicket
    date_field = "created"
    search_fields = ("ticket_no", "title", "profile_name", "wa_phone")

    def kpis(self, queryset):
        rows = list(queryset.values_list("created", "resolved_at", "closed_at"))
        # Matches the Complaint Audit's "completed": closed, else resolved.
        hours = [
            ((closed or resolved) - created).total_seconds() / 3600
            for created, resolved, closed in rows
            if created and (closed or resolved)
        ]
        total = len(rows)
        escalated = queryset.filter(
            unique_id__in=ComplaintEscalationHistory.objects.filter(is_deleted=False).values("ticket_id")
        ).count()
        return {
            "total": total,
            "resolved_rate": round(len(hours) / total * 100) if total else None,
            "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
            "escalated": escalated,
        }

    def breakdown(self, queryset):
        statuses = dict(ComplaintStatus.objects.values_list("unique_id", "status_code"))
        names = dict(ComplaintStatus.objects.values_list("status_code", "status_name"))
        counts = Counter(statuses.get(s) for s in queryset.values_list("status_id", flat=True))
        return self._slices(counts, names)

    def rows(self, records):
        rows = []
        for s in summarize_tickets(records):
            seconds = s["total_resolution_seconds"] or s["open_seconds"]
            rows.append({
                "id": s["unique_id"],
                "date": _iso(s["created"]),
                "ticket_no": s["ticket_no"],
                "category": s["category_name"],
                "user": s["assigned_staff_name"],
                "status": s["status_code"],
                "status_label": s["status_name"],
                # Created -> resolution, or time open so far if unresolved.
                "tat_hours": round(seconds / 3600) if seconds is not None else None,
                "resolved": s["total_resolution_seconds"] is not None,
                "project": s["project_name"],
            })
        return rows


TRAILS = {
    "common": CommonTrail(),
    "login": LoginTrail(),
    "access": AccessTrail(),
    "route": RouteTrail(),
    "complaint": ComplaintTrail(),
}


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------


def parse_days(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DAYS
    return days if days in ALLOWED_DAYS else DEFAULT_DAYS


def window(days):
    """The last `days` local days including today, and the same-length
    window just before it, as aware [start, end) datetimes."""
    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    tz = timezone.get_current_timezone()

    def at(day):
        return timezone.make_aware(datetime.combine(day, time.min), tz)

    end = at(today + timedelta(days=1))
    start = at(start_day)
    previous_start = at(start_day - timedelta(days=days))
    return start_day, today, start, end, previous_start


def in_range(trail, queryset, start, end):
    return queryset.filter(**{f"{trail.date_field}__gte": start, f"{trail.date_field}__lt": end})


def trend(trail, queryset, start_day, end_day):
    counts = Counter(
        timezone.localtime(value).date()
        for value in queryset.values_list(trail.date_field, flat=True)
        if value
    )
    days = (end_day - start_day).days + 1
    return [
        {"date": (day := start_day + timedelta(days=i)).isoformat(), "count": counts.get(day, 0)}
        for i in range(days)
    ]


def summary(trail, scoped, days):
    """Headline numbers for the window. The table's search does not narrow
    these, so the comparison with the previous window stays like-for-like."""
    start_day, end_day, start, end, previous_start = window(days)
    current = in_range(trail, scoped, start, end)
    return {
        "date_from": start_day.isoformat(),
        "date_to": end_day.isoformat(),
        "days": days,
        "kpis": trail.kpis(current),
        "previous_total": in_range(trail, scoped, previous_start, start).count(),
        "trend": trend(trail, current, start_day, end_day),
        "breakdown": trail.breakdown(current),
    }
