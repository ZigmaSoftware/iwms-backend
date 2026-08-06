"""Monthly waste collection analytics backed by confirmed DailyTripLog rows."""
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.monthly_weight_report import MonthlyWeightReport
from app.serializers.reports.waste_reports.monthly_weight_report_serializer import (
    MonthlyWeightReportSerializer,
)
from app.utils.waste_collection_report import build_waste_collection_report
from app.viewsets.reports.waste_reports.daily_waste_comparison_viewset import _comma_values
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class MonthlyWasteComparisonReportViewSet(CompanyScopedViewSet):
    permission_resource = "MonthlyWasteComparisonReport"
    queryset = MonthlyWeightReport.objects.select_related(
        "company_id", "project_id", "panchayat_id", "waste_type_id"
    )
    serializer_class = MonthlyWeightReportSerializer
    lookup_field = "unique_id"

    def list(self, request):
        queryset = DailyTripLog.objects.select_related(
            "company_id", "project_id", "panchayat_id"
        ).filter(
            is_deleted=False,
            log_status__in=[
                DailyTripLog.LOG_STATUS_SUBMITTED,
                DailyTripLog.LOG_STATUS_VERIFIED,
            ],
        )
        queryset = self.filter_queryset(queryset)

        month_value = request.query_params.get("month")
        date_filter = None
        if month_value:
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
            queryset = queryset.filter(waste_type_id_id=waste_type_id)

        payload = build_waste_collection_report(
            queryset,
            source=request.query_params.get("source", "bin").lower(),
            monthly=True,
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
