"""Daily waste collection analytics backed by confirmed DailyTripLog rows."""
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.daily_waste_comparison import DailyWasteComparison
from app.serializers.reports.waste_reports.daily_waste_comparison_serializer import (
    DailyWasteComparisonSerializer,
)
from app.utils.waste_collection_report import build_waste_collection_report
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


def _comma_values(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


class DailyWasteComparisonViewSet(CompanyScopedViewSet):
    permission_resource = "DailyWasteComparison"
    queryset = DailyWasteComparison.objects.select_related(
        "company_id", "project_id", "panchayat_id", "waste_type_id"
    )
    serializer_class = DailyWasteComparisonSerializer
    lookup_field = "unique_id"

    def list(self, request):
        queryset = DailyTripLog.objects.select_related(
            "company_id", "project_id", "panchayat_id"
        ).filter(is_deleted=False)
        queryset = self.filter_queryset(queryset)

        date_value = request.query_params.get("date")
        month_value = request.query_params.get("month")
        date_filter = None
        if date_value:
            queryset = queryset.filter(trip_date=date_value)
            date_filter = {"collection_date": date_value}
        elif month_value:
            try:
                year, month = month_value.split("-")
                queryset = queryset.filter(
                    trip_date__year=int(year), trip_date__month=int(month)
                )
                date_filter = {
                    "collection_date__year": int(year),
                    "collection_date__month": int(month),
                }
            except (TypeError, ValueError):
                pass

        panchayat_ids = _comma_values(request.query_params.get("panchayat_id"))
        if panchayat_ids:
            queryset = queryset.filter(panchayat_id_id__in=panchayat_ids)

        waste_type_id = request.query_params.get("waste_type_id")
        if waste_type_id:
            # Retains the existing endpoint's primary-waste-type filter.
            queryset = queryset.filter(waste_type_id_id=waste_type_id)

        payload = build_waste_collection_report(
            queryset,
            source=request.query_params.get("source", "bin").lower(),
            waste_type_id=waste_type_id,
            sort=request.query_params.get("sort", "weight").lower(),
            page=request.query_params.get("page"),
            limit=request.query_params.get("limit"),
            company_id=request.query_params.get("company_id"),
            project_id=request.query_params.get("project_id"),
            panchayat_ids=panchayat_ids or None,
            date_filter=date_filter,
        )
        return Response(payload)
