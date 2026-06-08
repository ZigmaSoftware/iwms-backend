"""
Panchayat Leader Dashboard API
Authenticated-only endpoint (no module permission check).
Returns the monthly waste comparison data locked to the leader's panchayat.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.reports.monthly_weight_report import MonthlyWeightReport
from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin


ZERO = Decimal("0")
TWO = Decimal("0.01")


def _rounded(value):
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def _percent(numerator, denominator):
    d = Decimal(str(denominator))
    if d == ZERO:
        return ZERO
    return _rounded(Decimal(str(numerator)) / d * Decimal("100"))


def _status(actual, agreed):
    a, g = Decimal(str(actual)), Decimal(str(agreed))
    if a > g:
        return "Surplus"
    if a < g:
        return "Deficit"
    return "On Target"


class LocalBodyDashboardViewSet(ViewSet):
    """
    Read-only monthly waste comparison report filtered to the
    authenticated panchayat leader's panchayat.
    """
    permission_classes = [IsAuthenticated]

    def _get_leader_panchayat(self, request):
        """Resolve the panchayat unique_id from the authenticated leader."""
        user = request.user
        if isinstance(user, PanchayatLeaderLogin):
            panchayat = getattr(user, "panchayat_id", None)
            if panchayat:
                return panchayat.unique_id
        return None

    def list(self, request):
        panchayat_unique_id = self._get_leader_panchayat(request)
        if not panchayat_unique_id:
            return Response(
                {"detail": "Panchayat not found for this leader."},
                status=403,
            )

        queryset = MonthlyWeightReport.objects.select_related(
            "company_id", "project_id", "panchayat_id", "waste_type_id"
        ).filter(panchayat_id=panchayat_unique_id)

        month = request.query_params.get("month")
        waste_type_id = request.query_params.get("waste_type_id")
        if month:
            queryset = queryset.filter(month=month)
        if waste_type_id:
            queryset = queryset.filter(waste_type_id=waste_type_id)

        grouped_rows = queryset.values(
            "unique_id",
            "company_id",
            "company_id__name",
            "project_id",
            "project_id__name",
            "month",
            "panchayat_id",
            "panchayat_id__panchayat_name",
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ).annotate(
            total_agreed_weight=Sum("agreed_weight_kg"),
            total_actual_weight=Sum("actual_weight_kg"),
            average_variance_percent=Avg("variance_percent"),
            total_trips=Sum("total_trips"),
            collection_points_covered=Sum("collection_points_covered"),
        )

        rows = []
        for row in grouped_rows:
            total_agreed = Decimal(str(row["total_agreed_weight"] or 0))
            total_actual = Decimal(str(row["total_actual_weight"] or 0))
            variance = total_actual - total_agreed
            total_trips = int(row["total_trips"] or 0)
            points = int(row["collection_points_covered"] or 0)

            rows.append({
                "unique_id": row["unique_id"],
                "company_id": row["company_id"],
                "company_name": row["company_id__name"],
                "project_id": row["project_id"],
                "project_name": row["project_id__name"],
                "month": row["month"],
                "panchayat_id": row["panchayat_id"],
                "panchayat_name": row["panchayat_id__panchayat_name"] or row["panchayat_id"],
                "waste_type_id": row["waste_type_id"],
                "waste_type": row["waste_type_id__waste_type_name"] or row["waste_type_id"],
                "total_agreed_weight": float(_rounded(total_agreed)),
                "total_actual_weight": float(_rounded(total_actual)),
                "variance_kg": float(_rounded(variance)),
                "variance_percent": float(_rounded(row["average_variance_percent"])),
                "report_status": _status(total_actual, total_agreed),
                "total_trips": total_trips,
                "collection_points_covered": points,
                "collection_efficiency_percent": float(_percent(total_actual, total_agreed)),
                "coverage_efficiency_percent": float(_percent(points, total_trips)),
                "average_weight_per_trip": float(
                    _rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
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
            "panchayat_name": rows[0]["panchayat_name"] if rows else "",
            "results": rows,
            "monthly_trends": self._monthly_trends(rows),
            "waste_type_breakdown": self._waste_type_breakdown(rows),
            "kpis": self._totals(rows),
        })

    def _monthly_trends(self, rows):
        trends = {}
        for row in rows:
            m = row["month"]
            trends.setdefault(m, {
                "month": m,
                "total_agreed_weight": 0,
                "total_actual_weight": 0,
                "variance_kg": 0,
                "total_trips": 0,
                "collection_points_covered": 0,
            })
            trends[m]["total_agreed_weight"] += row["total_agreed_weight"]
            trends[m]["total_actual_weight"] += row["total_actual_weight"]
            trends[m]["variance_kg"] += row["variance_kg"]
            trends[m]["total_trips"] += row["total_trips"]
            trends[m]["collection_points_covered"] += row["collection_points_covered"]
        return sorted(trends.values(), key=lambda t: str(t["month"]))

    def _waste_type_breakdown(self, rows):
        types = {}
        for row in rows:
            wt = row["waste_type"] or row["waste_type_id"]
            types.setdefault(wt, {
                "waste_type": wt,
                "total_agreed_weight": 0,
                "total_actual_weight": 0,
                "variance_kg": 0,
            })
            types[wt]["total_agreed_weight"] += row["total_agreed_weight"]
            types[wt]["total_actual_weight"] += row["total_actual_weight"]
            types[wt]["variance_kg"] += row["variance_kg"]
        return sorted(types.values(), key=lambda t: abs(t["variance_kg"]), reverse=True)

    def _totals(self, rows):
        total_agreed = sum(Decimal(str(r["total_agreed_weight"])) for r in rows)
        total_actual = sum(Decimal(str(r["total_actual_weight"])) for r in rows)
        total_trips = sum(r["total_trips"] for r in rows)
        total_points = sum(r["collection_points_covered"] for r in rows)
        return {
            "total_agreed_weight": float(_rounded(total_agreed)),
            "total_actual_weight": float(_rounded(total_actual)),
            "variance_kg": float(_rounded(total_actual - total_agreed)),
            "collection_efficiency_percent": float(_percent(total_actual, total_agreed)),
            "average_weight_per_trip": float(
                _rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "coverage_efficiency_percent": float(_percent(total_points, total_trips)),
            "total_trips": total_trips,
            "collection_points_covered": total_points,
            "report_status": _status(total_actual, total_agreed),
        }
