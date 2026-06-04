from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Sum
from rest_framework.response import Response

from app.models.schedule_masters import MonthlyWeightReport
from app.serializers.schedule_masters.monthly_weight_report_serializer import MonthlyWeightReportSerializer
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
    denominator = decimal_value(denominator)
    if denominator == ZERO:
        return ZERO
    return rounded((decimal_value(numerator) / denominator) * Decimal("100"))


def performance_status(actual, agreed):
    actual = decimal_value(actual)
    agreed = decimal_value(agreed)
    if actual > agreed:
        return "Surplus"
    if actual < agreed:
        return "Deficit"
    return "On Target"


class MonthlyWasteComparisonReportViewSet(CompanyScopedViewSet):
    permission_resource = "MonthlyWasteComparisonReport"
    queryset = MonthlyWeightReport.objects.select_related(
        "company_id", "project_id", "panchayat_id", "waste_type_id"
    )
    serializer_class = MonthlyWeightReportSerializer
    lookup_field = "unique_id"

    def list(self, request):
        queryset = MonthlyWeightReport.objects.select_related(
            "company_id", "project_id", "panchayat_id", "waste_type_id"
        )

        # CompanyScopedViewSet.filter_queryset handles company+project scoping for
        # company users; for superadmin it passes through without filtering.
        queryset = self.filter_queryset(queryset)

        # Superadmin: allow optional company / project filter via query params
        if self._is_platform_super_admin():
            company_param = request.query_params.get("company_id")
            project_param = request.query_params.get("project_id")
            if company_param:
                queryset = queryset.filter(company_id__unique_id=company_param)
            if project_param:
                queryset = queryset.filter(project_id__unique_id=project_param)
        else:
            # Company users can further narrow by project via query param
            project_param = request.query_params.get("project_id")
            if project_param:
                queryset = queryset.filter(project_id__unique_id=project_param)

        month = request.query_params.get("month")
        panchayat_id = request.query_params.get("panchayat_id")
        waste_type_id = request.query_params.get("waste_type_id")

        if month:
            queryset = queryset.filter(month=month)
        if panchayat_id:
            queryset = queryset.filter(panchayat_id=panchayat_id)
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
            total_agreed = decimal_value(row["total_agreed_weight"])
            total_actual = decimal_value(row["total_actual_weight"])
            variance = total_actual - total_agreed
            total_trips = int(row["total_trips"] or 0)
            points_covered = int(row["collection_points_covered"] or 0)

            rows.append(
                {
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
                    "total_agreed_weight": float(rounded(total_agreed)),
                    "total_actual_weight": float(rounded(total_actual)),
                    "variance_kg": float(rounded(variance)),
                    "variance_percent": float(rounded(row["average_variance_percent"])),
                    "report_status": performance_status(total_actual, total_agreed),
                    "total_trips": total_trips,
                    "collection_points_covered": points_covered,
                    "collection_efficiency_percent": float(percent(total_actual, total_agreed)),
                    "coverage_efficiency_percent": float(percent(points_covered, total_trips)),
                    "average_weight_per_trip": float(
                        rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
                    ),
                }
            )

        sort_mode = request.query_params.get("sort", "absolute").lower()
        if sort_mode == "deficit":
            rows.sort(key=lambda item: item["variance_kg"])
        elif sort_mode == "surplus":
            rows.sort(key=lambda item: item["variance_kg"], reverse=True)
        else:
            rows.sort(key=lambda item: abs(item["variance_kg"]), reverse=True)

        monthly_trends = self._build_monthly_trends(rows)
        panchayat_comparison = self._build_panchayat_comparison(rows)
        totals = self._build_totals(rows)

        return Response(
            {
                "results": rows,
                "monthly_trends": monthly_trends,
                "panchayat_comparison": panchayat_comparison,
                "kpis": totals,
            }
        )

    def _build_monthly_trends(self, rows):
        trends = {}
        for row in rows:
            month = row["month"]
            trends.setdefault(
                month,
                {
                    "month": month,
                    "total_agreed_weight": 0,
                    "total_actual_weight": 0,
                    "variance_kg": 0,
                    "total_trips": 0,
                    "collection_points_covered": 0,
                },
            )
            trends[month]["total_agreed_weight"] += row["total_agreed_weight"]
            trends[month]["total_actual_weight"] += row["total_actual_weight"]
            trends[month]["variance_kg"] += row["variance_kg"]
            trends[month]["total_trips"] += row["total_trips"]
            trends[month]["collection_points_covered"] += row["collection_points_covered"]

        return [
            {
                **item,
                "collection_efficiency_percent": float(
                    percent(item["total_actual_weight"], item["total_agreed_weight"])
                ),
                "average_weight_per_trip": float(
                    rounded(
                        Decimal(str(item["total_actual_weight"])) / Decimal(item["total_trips"])
                    )
                    if item["total_trips"]
                    else ZERO
                ),
            }
            for item in sorted(trends.values(), key=lambda trend: str(trend["month"]))
        ]

    def _build_panchayat_comparison(self, rows):
        panchayats = {}
        for row in rows:
            panchayat_id = row["panchayat_id"]
            panchayats.setdefault(
                panchayat_id,
                {
                    "panchayat_id": panchayat_id,
                    "panchayat_name": row["panchayat_name"],
                    "total_agreed_weight": 0,
                    "total_actual_weight": 0,
                    "variance_kg": 0,
                },
            )
            panchayats[panchayat_id]["total_agreed_weight"] += row["total_agreed_weight"]
            panchayats[panchayat_id]["total_actual_weight"] += row["total_actual_weight"]
            panchayats[panchayat_id]["variance_kg"] += row["variance_kg"]

        return sorted(
            (
                {
                    **item,
                    "collection_efficiency_percent": float(
                        percent(item["total_actual_weight"], item["total_agreed_weight"])
                    ),
                    "report_status": performance_status(
                        item["total_actual_weight"],
                        item["total_agreed_weight"],
                    ),
                }
                for item in panchayats.values()
            ),
            key=lambda item: abs(item["variance_kg"]),
            reverse=True,
        )

    def _build_totals(self, rows):
        total_agreed = sum(Decimal(str(row["total_agreed_weight"])) for row in rows)
        total_actual = sum(Decimal(str(row["total_actual_weight"])) for row in rows)
        total_trips = sum(row["total_trips"] for row in rows)
        total_points = sum(row["collection_points_covered"] for row in rows)

        return {
            "total_agreed_weight": float(rounded(total_agreed)),
            "total_actual_weight": float(rounded(total_actual)),
            "variance_kg": float(rounded(total_actual - total_agreed)),
            "collection_efficiency_percent": float(percent(total_actual, total_agreed)),
            "average_weight_per_trip": float(
                rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "coverage_efficiency_percent": float(percent(total_points, total_trips)),
            "total_trips": total_trips,
            "collection_points_covered": total_points,
            "report_status": performance_status(total_actual, total_agreed),
        }
