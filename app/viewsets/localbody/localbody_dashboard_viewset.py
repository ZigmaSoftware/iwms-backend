"""
Panchayat Leader Dashboard API
Authenticated-only endpoint — no module permission check (see AUTH_ONLY_SUFFIXES).
Returns:
  • Monthly waste comparison data  (from MonthlyWeightReport)
  • Day-wise waste collection       (from DailyWasteComparison)
  • Waste-type breakdown            (from DailyWasteComparison)
  • Individual daily rows           (for the table)
All data is locked to the authenticated leader's panchayat.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.schedule_masters.monthly_weight_report import MonthlyWeightReport
from app.models.schedule_masters.daily_waste_comparison import DailyWasteComparison


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
        daily_data    = self._daily_data(panchayat_uid, month)

        leader = self._get_leader(request)
        panchayat_name = getattr(getattr(leader, "panchayat_id", None), "panchayat_name", "") or ""

        return Response({
            "panchayat_name":       panchayat_name,

            # ── monthly comparison ──────────────────────────────────────
            "results":              monthly_data["results"],
            "monthly_trends":       monthly_data["monthly_trends"],
            "waste_type_breakdown": monthly_data["waste_type_breakdown"],
            "kpis":                 monthly_data["kpis"],

            # ── daily waste data ─────────────────────────────────────────
            "day_wise_collection":  daily_data["day_wise"],
            "trip_waste_types":     daily_data["waste_types"],
            "day_wise_breakdown":   daily_data["day_wise_breakdown"],
            "daily_rows":           daily_data["daily_rows"],
            "daily_kpis":           daily_data["daily_kpis"],
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

    # ── daily waste data (from DailyWasteComparison) ────────────────────

    def _daily_data(self, panchayat_uid, month):
        qs = DailyWasteComparison.objects.select_related(
            "waste_type_id", "panchayat_id", "company_id", "project_id"
        ).filter(
            panchayat_id=panchayat_uid,
        )

        if month:
            try:
                year, mon = month.split("-")
                qs = qs.filter(
                    collection_date__year=int(year),
                    collection_date__month=int(mon),
                )
            except ValueError:
                pass

        # ── per-date × per-waste-type breakdown ─────────────────────────
        # This drives all three daily charts (weight, trips, points per date).
        breakdown_raw = (
            qs.values("collection_date", "waste_type_id__waste_type_name")
            .annotate(
                actual_weight_kg = Sum("actual_weight_kg"),
                agreed_weight_kg = Sum("agreed_weight_kg"),
                trip_count       = Sum("total_trips"),
                points_covered   = Sum("collection_points_covered"),
            )
            .order_by("collection_date", "waste_type_id__waste_type_name")
        )
        day_wise_breakdown = [
            {
                "date":              str(r["collection_date"]),
                "waste_type":        r["waste_type_id__waste_type_name"] or "Unknown",
                "actual_weight_kg":  float(_r(r["actual_weight_kg"])),
                "agreed_weight_kg":  float(_r(r["agreed_weight_kg"])),
                "trip_count":        int(r["trip_count"] or 0),
                "points_covered":    int(r["points_covered"] or 0),
            }
            for r in breakdown_raw
        ]

        # ── day-wise totals (for summary / line chart) ───────────────────
        day_totals: dict = {}
        for r in day_wise_breakdown:
            d = r["date"]
            if d not in day_totals:
                day_totals[d] = {"date": d, "collected_weight_kg": 0.0, "trip_count": 0, "points_covered": 0}
            day_totals[d]["collected_weight_kg"] += r["actual_weight_kg"]
            day_totals[d]["trip_count"]          += r["trip_count"]
            day_totals[d]["points_covered"]      += r["points_covered"]
        day_wise = sorted(day_totals.values(), key=lambda x: x["date"])

        # ── waste-type overall totals (pie chart) ───────────────────────
        wt_totals: dict = {}
        for r in day_wise_breakdown:
            wt = r["waste_type"]
            if wt not in wt_totals:
                wt_totals[wt] = {"waste_type": wt, "collected_weight_kg": 0.0, "trip_count": 0}
            wt_totals[wt]["collected_weight_kg"] += r["actual_weight_kg"]
            wt_totals[wt]["trip_count"]          += r["trip_count"]
        waste_types = sorted(wt_totals.values(), key=lambda x: x["collected_weight_kg"], reverse=True)

        # ── individual DWC rows (for table) ──────────────────────────────
        rows_raw = (
            qs.values(
                "unique_id",
                "collection_date",
                "waste_type_id__waste_type_name",
                "agreed_weight_kg",
                "actual_weight_kg",
                "variance_kg",
                "variance_percent",
                "report_status",
                "total_trips",
                "collection_points_covered",
            )
            .order_by("-collection_date")[:300]
        )
        daily_rows = [
            {
                "unique_id":                   r["unique_id"],
                "date":                        str(r["collection_date"]),
                "waste_type":                  r["waste_type_id__waste_type_name"] or "—",
                "agreed_weight_kg":            float(_r(r["agreed_weight_kg"])),
                "actual_weight_kg":            float(_r(r["actual_weight_kg"])),
                "variance_kg":                 float(_r(r["variance_kg"])),
                "variance_percent":            float(_r(r["variance_percent"])),
                "report_status":               r["report_status"] or "—",
                "total_trips":                 int(r["total_trips"] or 0),
                "collection_points_covered":   int(r["collection_points_covered"] or 0),
            }
            for r in rows_raw
        ]

        # ── daily KPIs ───────────────────────────────────────────────────
        total_actual  = sum(Decimal(str(r["actual_weight_kg"])) for r in daily_rows)
        total_agreed  = sum(Decimal(str(r["agreed_weight_kg"])) for r in daily_rows)
        total_trips   = sum(r["total_trips"] for r in daily_rows)
        total_points  = sum(r["collection_points_covered"] for r in daily_rows)
        efficiency    = float(_pct(total_actual, total_agreed)) if total_agreed else 0.0

        daily_kpis = {
            "total_actual_kg":              float(_r(total_actual)),
            "total_agreed_kg":              float(_r(total_agreed)),
            "variance_kg":                  float(_r(total_actual - total_agreed)),
            "total_trips":                  total_trips,
            "collection_points_covered":    total_points,
            "collection_efficiency_percent": efficiency,
            "avg_weight_per_trip":          float(_r(total_actual / Decimal(total_trips)) if total_trips else ZERO),
        }

        return {
            "day_wise": day_wise,
            "waste_types": waste_types,
            "day_wise_breakdown": day_wise_breakdown,
            "daily_rows": daily_rows,
            "daily_kpis": daily_kpis,
        }
