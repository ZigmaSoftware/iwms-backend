"""
Daily Waste Comparison — computed live from DailyTripLog.

Data source: DailyTripLog (Submitted + Verified logs only)
  actual_weight_kg  = Sum(collected_weight_kg) per (date, panchayat, waste_type)
  agreed_weight_kg  = Panchayat.agreed_weight_kg (daily contract target)
  total_trips       = Count of trip logs in the group
  points_covered    = Count of distinct collection_point_id in the group
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Sum
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.serializers.schedule_masters.daily_waste_comparison_serializer import DailyWasteComparisonSerializer
from app.models.schedule_masters.daily_waste_comparison import DailyWasteComparison
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")


def decimal_value(value):
    if value is None:
        return ZERO
    return Decimal(str(value))


def rounded(value):
    return decimal_value(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def percent(numerator, denominator):
    d = decimal_value(denominator)
    if d == ZERO:
        return ZERO
    return rounded(decimal_value(numerator) / d * Decimal("100"))


def variance_pct(actual, agreed):
    agreed_d = decimal_value(agreed)
    if agreed_d == ZERO:
        return ZERO
    return rounded((decimal_value(actual) - agreed_d) / agreed_d * Decimal("100"))


def performance_status(actual, agreed):
    actual = decimal_value(actual)
    agreed = decimal_value(agreed)
    if actual > agreed:
        return "Surplus"
    if actual < agreed:
        return "Deficit"
    return "On Target"


class DailyWasteComparisonViewSet(CompanyScopedViewSet):
    permission_resource = "DailyWasteComparison"
    # Keep original queryset for retrieve/update/delete operations on the static table
    queryset = DailyWasteComparison.objects.select_related(
        "company_id", "project_id", "panchayat_id", "waste_type_id"
    )
    serializer_class = DailyWasteComparisonSerializer
    lookup_field = "unique_id"

    def list(self, request):
        # ── base queryset: only confirmed trip logs ──────────────────────
        queryset = DailyTripLog.objects.select_related(
            "company_id", "project_id", "panchayat_id", "waste_type_id",
        ).filter(
            is_deleted=False,
            log_status__in=[
                DailyTripLog.LOG_STATUS_SUBMITTED,
                DailyTripLog.LOG_STATUS_VERIFIED,
            ],
        )

        # ── company / project scoping (superadmin passes through) ────────
        queryset = self.filter_queryset(queryset)

        if self._is_platform_super_admin():
            company_param = request.query_params.get("company_id")
            project_param = request.query_params.get("project_id")
            if company_param:
                queryset = queryset.filter(company_id__unique_id=company_param)
            if project_param:
                queryset = queryset.filter(project_id__unique_id=project_param)
        else:
            project_param = request.query_params.get("project_id")
            if project_param:
                queryset = queryset.filter(project_id__unique_id=project_param)

        # ── date / month / panchayat / waste_type filters ────────────────
        date_param = request.query_params.get("date")
        month_param = request.query_params.get("month")
        panchayat_param = request.query_params.get("panchayat_id")
        waste_type_param = request.query_params.get("waste_type_id")

        if date_param:
            queryset = queryset.filter(trip_date=date_param)
        elif month_param:
            try:
                year, mon = month_param.split("-")
                queryset = queryset.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except (ValueError, AttributeError):
                pass

        if panchayat_param:
            queryset = queryset.filter(panchayat_id=panchayat_param)
        if waste_type_param:
            queryset = queryset.filter(waste_type_id=waste_type_param)

        # ── aggregate by (trip_date, panchayat, waste_type) ─────────────
        grouped_qs = queryset.values(
            "trip_date",
            "panchayat_id",
            "panchayat_id__panchayat_name",
            "panchayat_id__agreed_weight_kg",
            "waste_type_id",
            "waste_type_id__waste_type_name",
            "company_id",
            "company_id__name",
            "project_id",
            "project_id__name",
        ).annotate(
            total_actual_weight=Sum("collected_weight_kg"),
            total_trips=Count("unique_id"),
            collection_points_covered=Count("collection_point_id", distinct=True),
        )

        rows = []
        for row in grouped_qs:
            agreed = decimal_value(row["panchayat_id__agreed_weight_kg"])
            actual = decimal_value(row["total_actual_weight"])
            variance = actual - agreed
            total_trips = int(row["total_trips"] or 0)
            points = int(row["collection_points_covered"] or 0)

            unique_id = (
                f"DWC-{row['trip_date']}-{row['panchayat_id']}-{row['waste_type_id']}"
            )

            rows.append({
                "unique_id": unique_id,
                "company_id": row["company_id"],
                "company_name": row["company_id__name"],
                "project_id": row["project_id"],
                "project_name": row["project_id__name"],
                "collection_date": str(row["trip_date"]),
                "panchayat_id": row["panchayat_id"],
                "panchayat_name": (
                    row["panchayat_id__panchayat_name"] or row["panchayat_id"]
                ),
                "waste_type_id": row["waste_type_id"],
                "waste_type": (
                    row["waste_type_id__waste_type_name"] or row["waste_type_id"]
                ),
                "agreed_weight_kg": float(rounded(agreed)),
                "actual_weight_kg": float(rounded(actual)),
                "variance_kg": float(rounded(variance)),
                "variance_percent": float(variance_pct(actual, agreed)),
                "report_status": performance_status(actual, agreed),
                "total_trips": total_trips,
                "collection_points_covered": points,
                "collection_efficiency_percent": float(percent(actual, agreed)),
                "coverage_efficiency_percent": float(percent(points, total_trips)),
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(total_trips)) if total_trips else ZERO
                ),
            })

        sort_mode = request.query_params.get("sort", "absolute").lower()
        if sort_mode == "deficit":
            rows.sort(key=lambda r: r["variance_kg"])
        elif sort_mode == "surplus":
            rows.sort(key=lambda r: r["variance_kg"], reverse=True)
        else:
            rows.sort(key=lambda r: abs(r["variance_kg"]), reverse=True)

        return Response({
            "results": rows,
            "date_trends": self._build_date_trends(rows),
            "panchayat_comparison": self._build_panchayat_comparison(rows),
            "kpis": self._build_totals(rows),
        })

    # ── analytics helpers ────────────────────────────────────────────────

    def _build_date_trends(self, rows):
        trends = {}
        for row in rows:
            date = row["collection_date"]
            trends.setdefault(date, {
                "collection_date": date,
                "agreed_weight_kg": 0, "actual_weight_kg": 0,
                "variance_kg": 0, "total_trips": 0, "collection_points_covered": 0,
            })
            trends[date]["agreed_weight_kg"]          += row["agreed_weight_kg"]
            trends[date]["actual_weight_kg"]          += row["actual_weight_kg"]
            trends[date]["variance_kg"]               += row["variance_kg"]
            trends[date]["total_trips"]               += row["total_trips"]
            trends[date]["collection_points_covered"] += row["collection_points_covered"]

        return [
            {
                **item,
                "collection_efficiency_percent": float(
                    percent(item["actual_weight_kg"], item["agreed_weight_kg"])
                ),
                "average_weight_per_trip": float(
                    rounded(
                        Decimal(str(item["actual_weight_kg"])) / Decimal(item["total_trips"])
                    ) if item["total_trips"] else ZERO
                ),
            }
            for item in sorted(trends.values(), key=lambda x: str(x["collection_date"]))
        ]

    def _build_panchayat_comparison(self, rows):
        panchayats = {}
        for row in rows:
            pid = row["panchayat_id"]
            panchayats.setdefault(pid, {
                "panchayat_id": pid,
                "panchayat_name": row["panchayat_name"],
                "agreed_weight_kg": 0, "actual_weight_kg": 0, "variance_kg": 0,
            })
            panchayats[pid]["agreed_weight_kg"] += row["agreed_weight_kg"]
            panchayats[pid]["actual_weight_kg"] += row["actual_weight_kg"]
            panchayats[pid]["variance_kg"]      += row["variance_kg"]

        return sorted(
            (
                {
                    **item,
                    "collection_efficiency_percent": float(
                        percent(item["actual_weight_kg"], item["agreed_weight_kg"])
                    ),
                    "report_status": performance_status(
                        item["actual_weight_kg"], item["agreed_weight_kg"],
                    ),
                }
                for item in panchayats.values()
            ),
            key=lambda r: abs(r["variance_kg"]),
            reverse=True,
        )

    def _build_totals(self, rows):
        total_agreed = sum(Decimal(str(r["agreed_weight_kg"])) for r in rows)
        total_actual = sum(Decimal(str(r["actual_weight_kg"])) for r in rows)
        total_trips  = sum(r["total_trips"] for r in rows)
        total_points = sum(r["collection_points_covered"] for r in rows)

        return {
            "total_agreed_weight_kg":          float(rounded(total_agreed)),
            "total_actual_weight_kg":          float(rounded(total_actual)),
            "variance_kg":                     float(rounded(total_actual - total_agreed)),
            "collection_efficiency_percent":   float(percent(total_actual, total_agreed)),
            "average_weight_per_trip":         float(
                rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "coverage_efficiency_percent":     float(percent(total_points, total_trips)),
            "total_trips":                     total_trips,
            "collection_points_covered":       total_points,
            "report_status":                   performance_status(total_actual, total_agreed),
        }
