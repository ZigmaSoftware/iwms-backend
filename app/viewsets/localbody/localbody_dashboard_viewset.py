"""
Panchayat Leader Dashboard API
Authenticated-only endpoint — no module permission check (see AUTH_ONLY_SUFFIXES).
Returns:
  • Monthly waste comparison data  (from MonthlyWeightReport)
  • Day-wise waste collection       (from DailyTripLog)
  • Waste-type breakdown per trip   (from DailyTripLog)
  • Individual trip log rows        (for the table)
All data is locked to the authenticated leader's panchayat.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.reports.monthly_weight_report import MonthlyWeightReport
from app.models.schedule_masters.daily_trip_log import DailyTripLog


ZERO = Decimal("0")
TWO  = Decimal("0.01")


def _r(value):
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def _pct(num, den):
    d = Decimal(str(den))
    if d == ZERO:
        return ZERO
    return _r(Decimal(str(num)) / d * Decimal("100"))


def _status(actual, agreed):
    a, g = Decimal(str(actual)), Decimal(str(agreed))
    if a > g:
        return "Surplus"
    if a < g:
        return "Deficit"
    return "On Target"


class LocalBodyDashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    # ── helpers ─────────────────────────────────────────────────────────

    def _get_leader(self, request):
        user = request.user
        if isinstance(user, PanchayatLeaderLogin):
            return user
        return None

    def _get_panchayat_id(self, request):
        leader = self._get_leader(request)
        if leader:
            panchayat = getattr(leader, "panchayat_id", None)
            if panchayat:
                return panchayat.unique_id
        return None

    # ── main endpoint ───────────────────────────────────────────────────

    def list(self, request):
        panchayat_uid = self._get_panchayat_id(request)
        if not panchayat_uid:
            return Response({"detail": "Panchayat not found for this leader."}, status=403)

        month = request.query_params.get("month", "")
        sort  = request.query_params.get("sort", "absolute").lower()

        monthly_data  = self._monthly_report(panchayat_uid, month, sort)
        daily_data    = self._daily_trips(panchayat_uid, month)

        leader = self._get_leader(request)
        panchayat_name = getattr(getattr(leader, "panchayat_id", None), "panchayat_name", "") or ""

        return Response({
            "panchayat_name":       panchayat_name,

            # ── monthly comparison ──────────────────────────────────────
            "results":              monthly_data["results"],
            "monthly_trends":       monthly_data["monthly_trends"],
            "waste_type_breakdown": monthly_data["waste_type_breakdown"],
            "kpis":                 monthly_data["kpis"],

            # ── daily trip logs ─────────────────────────────────────────
            "day_wise_collection":  daily_data["day_wise"],
            "trip_waste_types":     daily_data["waste_types"],
            "trip_logs":            daily_data["logs"],
            "trip_kpis":            daily_data["trip_kpis"],
        })

    # ── monthly report (from MonthlyWeightReport) ───────────────────────

    def _monthly_report(self, panchayat_uid, month, sort):
        qs = MonthlyWeightReport.objects.select_related(
            "company_id", "project_id", "panchayat_id", "waste_type_id"
        ).filter(panchayat_id=panchayat_uid)

        if month:
            qs = qs.filter(month=month)

        grouped = qs.values(
            "unique_id",
            "company_id", "company_id__name",
            "project_id", "project_id__name",
            "month",
            "panchayat_id", "panchayat_id__panchayat_name",
            "waste_type_id", "waste_type_id__waste_type_name",
        ).annotate(
            total_agreed_weight   = Sum("agreed_weight_kg"),
            total_actual_weight   = Sum("actual_weight_kg"),
            average_variance_pct  = Avg("variance_percent"),
            total_trips           = Sum("total_trips"),
            collection_points     = Sum("collection_points_covered"),
        )

        rows = []
        for row in grouped:
            agreed  = Decimal(str(row["total_agreed_weight"] or 0))
            actual  = Decimal(str(row["total_actual_weight"] or 0))
            var     = actual - agreed
            trips   = int(row["total_trips"] or 0)
            points  = int(row["collection_points"] or 0)
            rows.append({
                "unique_id":                    row["unique_id"],
                "company_id":                   row["company_id"],
                "company_name":                 row["company_id__name"],
                "project_id":                   row["project_id"],
                "project_name":                 row["project_id__name"],
                "month":                        row["month"],
                "panchayat_id":                 row["panchayat_id"],
                "panchayat_name":               row["panchayat_id__panchayat_name"] or row["panchayat_id"],
                "waste_type_id":                row["waste_type_id"],
                "waste_type":                   row["waste_type_id__waste_type_name"] or row["waste_type_id"],
                "total_agreed_weight":          float(_r(agreed)),
                "total_actual_weight":          float(_r(actual)),
                "variance_kg":                  float(_r(var)),
                "variance_percent":             float(_r(row["average_variance_pct"])),
                "report_status":                _status(actual, agreed),
                "total_trips":                  trips,
                "collection_points_covered":    points,
                "collection_efficiency_percent": float(_pct(actual, agreed)),
                "coverage_efficiency_percent":  float(_pct(points, trips)),
                "average_weight_per_trip":      float(_r(actual / Decimal(trips)) if trips else ZERO),
            })

        if sort == "deficit":
            rows.sort(key=lambda r: r["variance_kg"])
        elif sort == "surplus":
            rows.sort(key=lambda r: r["variance_kg"], reverse=True)
        else:
            rows.sort(key=lambda r: abs(r["variance_kg"]), reverse=True)

        return {
            "results":              rows,
            "monthly_trends":       self._monthly_trends(rows),
            "waste_type_breakdown": self._waste_breakdown(rows),
            "kpis":                 self._totals(rows),
        }

    def _monthly_trends(self, rows):
        t = {}
        for r in rows:
            m = r["month"]
            t.setdefault(m, {"month": m, "total_agreed_weight": 0, "total_actual_weight": 0,
                             "variance_kg": 0, "total_trips": 0, "collection_points_covered": 0})
            t[m]["total_agreed_weight"]        += r["total_agreed_weight"]
            t[m]["total_actual_weight"]        += r["total_actual_weight"]
            t[m]["variance_kg"]               += r["variance_kg"]
            t[m]["total_trips"]               += r["total_trips"]
            t[m]["collection_points_covered"] += r["collection_points_covered"]
        return sorted(t.values(), key=lambda x: str(x["month"]))

    def _waste_breakdown(self, rows):
        t = {}
        for r in rows:
            wt = r["waste_type"] or r["waste_type_id"]
            t.setdefault(wt, {"waste_type": wt, "total_agreed_weight": 0,
                              "total_actual_weight": 0, "variance_kg": 0})
            t[wt]["total_agreed_weight"] += r["total_agreed_weight"]
            t[wt]["total_actual_weight"] += r["total_actual_weight"]
            t[wt]["variance_kg"]         += r["variance_kg"]
        return sorted(t.values(), key=lambda x: abs(x["variance_kg"]), reverse=True)

    def _totals(self, rows):
        agreed  = sum(Decimal(str(r["total_agreed_weight"])) for r in rows)
        actual  = sum(Decimal(str(r["total_actual_weight"])) for r in rows)
        trips   = sum(r["total_trips"] for r in rows)
        points  = sum(r["collection_points_covered"] for r in rows)
        return {
            "total_agreed_weight":           float(_r(agreed)),
            "total_actual_weight":           float(_r(actual)),
            "variance_kg":                   float(_r(actual - agreed)),
            "collection_efficiency_percent": float(_pct(actual, agreed)),
            "average_weight_per_trip":       float(_r(actual / Decimal(trips)) if trips else ZERO),
            "coverage_efficiency_percent":   float(_pct(points, trips)),
            "total_trips":                   trips,
            "collection_points_covered":     points,
            "report_status":                 _status(actual, agreed),
        }

    # ── daily trip data (from DailyTripLog) ─────────────────────────────

    def _daily_trips(self, panchayat_uid, month):
        qs = DailyTripLog.objects.select_related(
            "waste_type_id", "collection_point_id", "driver_id"
        ).filter(
            panchayat_id=panchayat_uid,
            is_deleted=False,
        )

        if month:
            try:
                year, mon = month.split("-")
                qs = qs.filter(trip_date__year=int(year), trip_date__month=int(mon))
            except ValueError:
                pass

        # ── day-wise aggregation ─────────────────────────────────────────
        day_wise_raw = (
            qs.values("trip_date")
            .annotate(
                collected_weight_kg = Sum("collected_weight_kg"),
                trip_count          = Count("unique_id"),
                verified_count      = Count("unique_id", filter=__import__("django.db.models", fromlist=["Q"]).Q(log_status="Verified")),
            )
            .order_by("trip_date")
        )
        day_wise = [
            {
                "date":                 str(r["trip_date"]),
                "collected_weight_kg":  float(_r(r["collected_weight_kg"])),
                "trip_count":           r["trip_count"],
                "verified_count":       r["verified_count"],
            }
            for r in day_wise_raw
        ]

        # ── waste-type aggregation ───────────────────────────────────────
        waste_raw = (
            qs.values("waste_type_id__waste_type_name")
            .annotate(
                collected_weight_kg = Sum("collected_weight_kg"),
                trip_count          = Count("unique_id"),
            )
            .order_by("-collected_weight_kg")
        )
        waste_types = [
            {
                "waste_type":           r["waste_type_id__waste_type_name"] or "Unknown",
                "collected_weight_kg":  float(_r(r["collected_weight_kg"])),
                "trip_count":           r["trip_count"],
            }
            for r in waste_raw
        ]

        # ── individual log rows (for table) ─────────────────────────────
        logs_raw = (
            qs.values(
                "unique_id",
                "trip_date",
                "waste_type_id__waste_type_name",
                "collected_weight_kg",
                "log_status",
                "collection_point_id__cp_name",
                "driver_id__employee_name",
                "actual_start_time",
                "actual_end_time",
            )
            .order_by("-trip_date")[:300]
        )
        logs = [
            {
                "unique_id":            r["unique_id"],
                "trip_date":            str(r["trip_date"]),
                "waste_type":           r["waste_type_id__waste_type_name"] or "—",
                "collected_weight_kg":  float(_r(r["collected_weight_kg"])),
                "log_status":           r["log_status"],
                "collection_point":     r["collection_point_id__cp_name"] or "—",
                "driver":               r["driver_id__employee_name"] or "—",
                "actual_start_time":    str(r["actual_start_time"]) if r["actual_start_time"] else None,
                "actual_end_time":      str(r["actual_end_time"])   if r["actual_end_time"]   else None,
            }
            for r in logs_raw
        ]

        # ── trip-level KPIs ──────────────────────────────────────────────
        total_weight = sum(Decimal(str(r["collected_weight_kg"])) for r in logs)
        total_trips  = len(logs)
        verified     = sum(1 for r in logs if r["log_status"] == "Verified")
        submitted    = sum(1 for r in logs if r["log_status"] == "Submitted")
        draft        = sum(1 for r in logs if r["log_status"] == "Draft")

        trip_kpis = {
            "total_collected_kg":   float(_r(total_weight)),
            "total_trips":          total_trips,
            "verified_trips":       verified,
            "submitted_trips":      submitted,
            "draft_trips":          draft,
            "avg_weight_per_trip":  float(_r(total_weight / Decimal(total_trips)) if total_trips else ZERO),
        }

        return {"day_wise": day_wise, "waste_types": waste_types, "logs": logs, "trip_kpis": trip_kpis}
