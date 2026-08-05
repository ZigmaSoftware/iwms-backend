"""Standalone household waste — WasteCollection rows with no trip_assignment_id.

DailyTripLog.trip_assignment_id is a required OneToOneField, so a
WasteCollection entered with no trip assignment (the "None (no assignment)"
option on the Waste Collected Data form) never gets a DailyTripLog at all —
it would otherwise be invisible to the Daily/Monthly Waste Collection
reports, which are built entirely from DailyTripLog. This module aggregates
those rows directly so they still count towards the same totals/trends/
waste-type breakdown as trip-linked collections.
"""
from decimal import Decimal

from django.db.models import Sum

from app.utils.waste_type_breakdown import (
    HOUSEHOLD_WASTE_TYPE_FALLBACK_ID_PREFIX,
    HOUSEHOLD_WASTE_TYPE_NAMES,
)


def _scoped_queryset(company_id=None, project_id=None, panchayat_ids=None, date_filter=None):
    from app.models.customers.wastecollection import WasteCollection

    queryset = WasteCollection.objects.filter(
        trip_assignment_id__isnull=True,
        is_deleted=False,
    ).select_related("customer", "customer__panchayat_id", "company_id", "project_id")
    if company_id:
        queryset = queryset.filter(company_id__unique_id=company_id)
    if project_id:
        queryset = queryset.filter(project_id__unique_id=project_id)
    if panchayat_ids:
        queryset = queryset.filter(customer__panchayat_id__unique_id__in=panchayat_ids)
    if date_filter:
        queryset = queryset.filter(**date_filter)
    return queryset


def household_only_location_rows(
    *, monthly, company_id=None, project_id=None, panchayat_ids=None, date_filter=None,
):
    """(period, company_id, project_id, panchayat_id) -> weight/trips/points, for
    rows with no trip_assignment_id — merged into the trip-based totals."""
    queryset = _scoped_queryset(company_id, project_id, panchayat_ids, date_filter)
    group_fields = [
        "collection_date",
        "company_id",
        "company_id__name",
        "project_id",
        "project_id__name",
        "customer__panchayat_id",
        "customer__panchayat_id__panchayat_name",
    ]
    rows = queryset.values(*group_fields).annotate(weight=Sum("total_quantity"))

    result = []
    for row in rows:
        panchayat_id = row["customer__panchayat_id"]
        if not panchayat_id:
            continue
        period = _period(row["collection_date"], monthly)
        visit_count = queryset.filter(
            collection_date=row["collection_date"],
            company_id=row["company_id"],
            project_id=row["project_id"],
            customer__panchayat_id=panchayat_id,
        ).count()
        result.append({
            "period": period,
            "company_id": row["company_id"],
            "company_name": row["company_id__name"],
            "project_id": row["project_id"],
            "project_name": row["project_id__name"],
            "panchayat_id": panchayat_id,
            "panchayat_name": row["customer__panchayat_id__panchayat_name"] or panchayat_id,
            "weight": Decimal(str(row["weight"] or 0)),
            "trips": visit_count,
            "points": 0,
        })
    return result


def household_only_type_rows(
    *, monthly, waste_type_id=None, company_id=None, project_id=None,
    panchayat_ids=None, date_filter=None,
):
    """Per-(period, company, project, panchayat, waste_type) weight buckets
    for standalone household rows, keyed to line up with type_buckets in
    waste_collection_report.build_waste_collection_report."""
    from app.models.user_creations.waste_collection_bluetooth import WasteType

    queryset = _scoped_queryset(company_id, project_id, panchayat_ids, date_filter)
    group_fields = [
        "collection_date",
        "company_id",
        "company_id__name",
        "project_id",
        "project_id__name",
        "customer__panchayat_id",
        "customer__panchayat_id__panchayat_name",
    ]
    rows = queryset.values(*group_fields).annotate(
        **{field: Sum(field) for field in HOUSEHOLD_WASTE_TYPE_NAMES}
    )
    masters = {
        item.waste_type_name: item
        for item in WasteType.objects.filter(is_deleted=False)
    }

    result = []
    for row in rows:
        panchayat_id = row["customer__panchayat_id"]
        if not panchayat_id:
            continue
        period = _period(row["collection_date"], monthly)
        common = {
            "period": period,
            "company_id": row["company_id"],
            "company_name": row["company_id__name"],
            "project_id": row["project_id"],
            "project_name": row["project_id__name"],
            "panchayat_id": panchayat_id,
            "panchayat_name": row["customer__panchayat_id__panchayat_name"] or panchayat_id,
        }
        for field, label in HOUSEHOLD_WASTE_TYPE_NAMES.items():
            weight = row.get(field)
            if not weight:
                continue
            master = masters.get(label)
            wt_id = master.unique_id if master else f"{HOUSEHOLD_WASTE_TYPE_FALLBACK_ID_PREFIX}-{field}"
            if waste_type_id and str(wt_id) != str(waste_type_id):
                continue
            result.append({
                **common,
                "waste_type_id": wt_id,
                "waste_type": master.waste_type_name if master else label,
                "weight": Decimal(str(weight)),
            })
    return result


def _period(date, monthly):
    return f"{date.year}-{date.month:02d}" if monthly else str(date)
