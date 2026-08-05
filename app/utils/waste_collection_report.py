from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from app.utils.waste_type_breakdown import bulk_waste_type_rows_for_trip_assignments
from app.utils.household_waste_breakdown import (
    household_only_location_rows,
    household_only_type_rows,
)


ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")
UNCLASSIFIED_WASTE_TYPE_ID = "UNCLASSIFIED"
UNCLASSIFIED_WASTE_TYPE_NAME = "Unclassified"


def decimal_value(value):
    return ZERO if value is None else Decimal(str(value))


def rounded(value):
    return decimal_value(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def percent(numerator, denominator):
    denominator = decimal_value(denominator)
    if not denominator:
        return ZERO
    return rounded(decimal_value(numerator) / denominator * Decimal("100"))


def _weight_expression(source):
    if source == "household":
        return Coalesce(
            F("household_collected_weight_kg"),
            Value(0, output_field=DecimalField()),
        )
    if source == "all":
        return (
            Coalesce(F("collected_weight_kg"), Value(0, output_field=DecimalField()))
            + Coalesce(
                F("household_collected_weight_kg"),
                Value(0, output_field=DecimalField()),
            )
        )
    return Coalesce(
        F("collected_weight_kg"), Value(0, output_field=DecimalField())
    )


def _period(row, monthly):
    date = row["trip_date"]
    return f"{date.year}-{date.month:02d}" if monthly else str(date)


def _paginate(rows, page_param, limit_param):
    if page_param is None and limit_param is None:
        return rows
    try:
        page = max(int(page_param or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        limit = max(1, min(int(limit_param or 20), 500))
    except (TypeError, ValueError):
        limit = 20
    offset = (page - 1) * limit
    return rows[offset:offset + limit]


def build_waste_collection_report(
    queryset,
    *,
    source,
    monthly=False,
    waste_type_id=None,
    sort="weight",
    page=None,
    limit=None,
    company_id=None,
    project_id=None,
    panchayat_ids=None,
    date_filter=None,
):
    """Build collection analytics without multiplying trip-level metrics."""
    source = source if source in {"bin", "household", "all"} else "bin"
    weight_expression = _weight_expression(source)

    group_fields = [
        "trip_date",
        "company_id",
        "company_id__name",
        "project_id",
        "project_id__name",
        "panchayat_id",
        "panchayat_id__panchayat_name",
    ]
    location_qs = queryset.values(*group_fields).annotate(
        total_actual_weight=Sum(
            ExpressionWrapper(
                weight_expression,
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        ),
        total_trips=Count("unique_id", distinct=True),
        collection_points_covered=Count("collection_point_id", distinct=True),
    )

    locations = {}
    for raw in location_qs:
        if not raw["panchayat_id"]:
            continue
        period = _period(raw, monthly)
        key = (
            period,
            raw["company_id"],
            raw["project_id"],
            raw["panchayat_id"],
        )
        bucket = locations.setdefault(key, {
            "period": period,
            "company_id": raw["company_id"],
            "company_name": raw["company_id__name"],
            "project_id": raw["project_id"],
            "project_name": raw["project_id__name"],
            "panchayat_id": raw["panchayat_id"],
            "panchayat_name": raw["panchayat_id__panchayat_name"] or raw["panchayat_id"],
            "weight": ZERO,
            "trips": 0,
            "points": 0,
        })
        bucket["weight"] += decimal_value(raw["total_actual_weight"])
        bucket["trips"] += int(raw["total_trips"] or 0)
        bucket["points"] += int(raw["collection_points_covered"] or 0)

    # Standalone household collections (no trip_assignment_id) have no
    # DailyTripLog row and are otherwise invisible to this report.
    if source in ("household", "all"):
        for hh in household_only_location_rows(
            monthly=monthly,
            company_id=company_id,
            project_id=project_id,
            panchayat_ids=panchayat_ids,
            date_filter=date_filter,
        ):
            key = (hh["period"], hh["company_id"], hh["project_id"], hh["panchayat_id"])
            bucket = locations.setdefault(key, {
                "period": hh["period"],
                "company_id": hh["company_id"],
                "company_name": hh["company_name"],
                "project_id": hh["project_id"],
                "project_name": hh["project_name"],
                "panchayat_id": hh["panchayat_id"],
                "panchayat_name": hh["panchayat_name"],
                "weight": ZERO,
                "trips": 0,
                "points": 0,
            })
            bucket["weight"] += hh["weight"]
            bucket["trips"] += hh["trips"]

    trip_info_rows = list(queryset.values(
        "trip_assignment_id_id",
        "trip_date",
        "company_id",
        "company_id__name",
        "project_id",
        "project_id__name",
        "panchayat_id",
        "panchayat_id__panchayat_name",
        "collection_point_id",
        "collected_weight_kg",
        "household_collected_weight_kg",
    ))
    info_by_assignment = {
        row["trip_assignment_id_id"]: row for row in trip_info_rows
    }
    assignment_ids = list(info_by_assignment)
    waste_rows = bulk_waste_type_rows_for_trip_assignments(
        assignment_ids,
        source=source,
        extra_group_by=("trip_date",),
    )
    if waste_type_id:
        waste_rows = [
            row for row in waste_rows
            if str(row["waste_type_id"]) == str(waste_type_id)
        ]

    type_buckets = {}

    def add_type_row(info, wt_id, wt_name, weight, assignment_id):
        if not info or not info["panchayat_id"]:
            return
        if decimal_value(weight) == ZERO:
            return
        period = _period(info, monthly)
        key = (
            period,
            info["company_id"],
            info["project_id"],
            info["panchayat_id"],
            wt_id,
        )
        bucket = type_buckets.setdefault(key, {
            "period": period,
            "company_id": info["company_id"],
            "company_name": info["company_id__name"],
            "project_id": info["project_id"],
            "project_name": info["project_id__name"],
            "panchayat_id": info["panchayat_id"],
            "panchayat_name": info["panchayat_id__panchayat_name"] or info["panchayat_id"],
            "waste_type_id": wt_id,
            "waste_type": wt_name,
            "weight": ZERO,
            "assignments": set(),
            "points": set(),
        })
        bucket["weight"] += decimal_value(weight)
        bucket["assignments"].add(assignment_id)
        if info["collection_point_id"]:
            bucket["points"].add(info["collection_point_id"])

    for waste_row in waste_rows:
        assignment_id = waste_row["trip_assignment_id"]
        info = info_by_assignment.get(assignment_id)
        if info and str(info["trip_date"]) == str(waste_row["trip_date"]):
            add_type_row(
                info,
                waste_row["waste_type_id"],
                waste_row["waste_type_name"],
                waste_row["weight_kg"],
                assignment_id,
            )

    if not waste_type_id:
        classified_ids = {row["trip_assignment_id"] for row in waste_rows}
        for assignment_id, info in info_by_assignment.items():
            if assignment_id in classified_ids:
                continue
            if source == "household":
                weight = info["household_collected_weight_kg"]
            elif source == "all":
                weight = decimal_value(info["collected_weight_kg"]) + decimal_value(
                    info["household_collected_weight_kg"]
                )
            else:
                weight = info["collected_weight_kg"]
            add_type_row(
                info,
                UNCLASSIFIED_WASTE_TYPE_ID,
                UNCLASSIFIED_WASTE_TYPE_NAME,
                weight,
                assignment_id,
            )

    if source in ("household", "all"):
        for hh in household_only_type_rows(
            monthly=monthly,
            waste_type_id=waste_type_id,
            company_id=company_id,
            project_id=project_id,
            panchayat_ids=panchayat_ids,
            date_filter=date_filter,
        ):
            key = (
                hh["period"], hh["company_id"], hh["project_id"],
                hh["panchayat_id"], hh["waste_type_id"],
            )
            bucket = type_buckets.setdefault(key, {
                "period": hh["period"],
                "company_id": hh["company_id"],
                "company_name": hh["company_name"],
                "project_id": hh["project_id"],
                "project_name": hh["project_name"],
                "panchayat_id": hh["panchayat_id"],
                "panchayat_name": hh["panchayat_name"],
                "waste_type_id": hh["waste_type_id"],
                "waste_type": hh["waste_type"],
                "weight": ZERO,
                "assignments": set(),
                "points": set(),
            })
            bucket["weight"] += hh["weight"]
            # No trip_assignment_id exists for these rows — count each
            # (period, panchayat, waste_type) bucket itself as one visit.
            bucket["assignments"].add(key)

    rows = []
    for bucket in type_buckets.values():
        trips = len(bucket["assignments"])
        weight = rounded(bucket["weight"])
        common = {
            "company_id": bucket["company_id"],
            "company_name": bucket["company_name"],
            "project_id": bucket["project_id"],
            "project_name": bucket["project_name"],
            "panchayat_id": bucket["panchayat_id"],
            "panchayat_name": bucket["panchayat_name"],
            "local_body_field": "panchayat",
            "local_body_type": "Panchayat",
            "local_body_id": bucket["panchayat_id"],
            "local_body_name": bucket["panchayat_name"],
            "waste_type_id": bucket["waste_type_id"],
            "waste_type": bucket["waste_type"],
            "total_trips": trips,
            "collection_points_covered": len(bucket["points"]),
            "average_weight_per_trip": float(rounded(weight / trips) if trips else ZERO),
        }
        if monthly:
            rows.append({
                "unique_id": f"MWR-{bucket['period']}-{bucket['panchayat_id']}-{bucket['waste_type_id']}",
                "month": bucket["period"],
                "total_actual_weight": float(weight),
                # Backward-compatible legacy comparison fields.
                "total_agreed_weight": 0.0,
                "variance_kg": float(weight),
                "variance_percent": 0.0,
                "collection_efficiency_percent": 0.0,
                "coverage_efficiency_percent": 0.0,
                "report_status": "Collected",
                **common,
            })
        else:
            rows.append({
                "unique_id": f"DWC-{bucket['period']}-{bucket['panchayat_id']}-{bucket['waste_type_id']}",
                "collection_date": bucket["period"],
                "actual_weight_kg": float(weight),
                # Backward-compatible legacy comparison fields.
                "agreed_weight_kg": 0.0,
                "variance_kg": float(weight),
                "variance_percent": 0.0,
                "collection_efficiency_percent": 0.0,
                "coverage_efficiency_percent": 0.0,
                "report_status": "Collected",
                **common,
            })

    weight_key = "total_actual_weight" if monthly else "actual_weight_kg"
    if sort == "trips":
        rows.sort(key=lambda row: row["total_trips"], reverse=True)
    else:
        rows.sort(key=lambda row: row[weight_key], reverse=True)

    trends = defaultdict(lambda: {"weight": ZERO, "trips": 0, "points": 0})
    comparisons = {}
    for location in locations.values():
        trend = trends[location["period"]]
        trend["weight"] += location["weight"]
        trend["trips"] += location["trips"]
        trend["points"] += location["points"]
        pid = location["panchayat_id"]
        comparison = comparisons.setdefault(pid, {
            "panchayat_id": pid,
            "panchayat_name": location["panchayat_name"],
            "weight": ZERO,
            "trips": 0,
            "points": 0,
        })
        comparison["weight"] += location["weight"]
        comparison["trips"] += location["trips"]
        comparison["points"] += location["points"]

    trend_rows = []
    for period, item in sorted(trends.items()):
        value = float(rounded(item["weight"]))
        trend_rows.append({
            ("month" if monthly else "collection_date"): period,
            weight_key: value,
            "total_trips": item["trips"],
            "collection_points_covered": item["points"],
            "average_weight_per_trip": float(
                rounded(item["weight"] / item["trips"]) if item["trips"] else ZERO
            ),
        })

    comparison_rows = []
    for item in comparisons.values():
        value = float(rounded(item["weight"]))
        comparison_rows.append({
            "panchayat_id": item["panchayat_id"],
            "panchayat_name": item["panchayat_name"],
            "local_body_field": "panchayat",
            "local_body_type": "Panchayat",
            "local_body_id": item["panchayat_id"],
            "local_body_name": item["panchayat_name"],
            weight_key: value,
            "total_trips": item["trips"],
            "collection_points_covered": item["points"],
            "average_weight_per_trip": float(
                rounded(item["weight"] / item["trips"]) if item["trips"] else ZERO
            ),
        })
    comparison_rows.sort(key=lambda row: row[weight_key], reverse=True)

    breakdown = {}
    for row in rows:
        item = breakdown.setdefault(row["waste_type_id"], {
            "waste_type_id": row["waste_type_id"],
            "waste_type": row["waste_type"],
            "weight": ZERO,
            "trips": 0,
            "points": 0,
            "panchayats": set(),
        })
        item["weight"] += decimal_value(row[weight_key])
        item["trips"] += row["total_trips"]
        item["points"] += row["collection_points_covered"]
        item["panchayats"].add(row["panchayat_id"])
    breakdown_total = sum((item["weight"] for item in breakdown.values()), ZERO)
    breakdown_rows = [{
        "waste_type_id": item["waste_type_id"],
        "waste_type": item["waste_type"],
        "actual_weight_kg": float(rounded(item["weight"])),
        "total_actual_weight": float(rounded(item["weight"])),
        "share_percent": float(percent(item["weight"], breakdown_total)),
        "total_trips": item["trips"],
        "collection_points_covered": item["points"],
        "panchayat_count": len(item["panchayats"]),
    } for item in breakdown.values()]
    breakdown_rows.sort(key=lambda row: row["actual_weight_kg"], reverse=True)

    total_weight = sum((item["weight"] for item in locations.values()), ZERO)
    total_trips = sum(item["trips"] for item in locations.values())
    total_points = sum(item["points"] for item in locations.values())
    kpis = {
        "total_actual_weight_kg": float(rounded(total_weight)),
        "total_actual_weight": float(rounded(total_weight)),
        "average_weight_per_trip": float(
            rounded(total_weight / total_trips) if total_trips else ZERO
        ),
        "total_trips": total_trips,
        "collection_points_covered": total_points,
        "waste_type_count": len(breakdown_rows),
        "panchayat_count": len(comparisons),
        "local_body_count": len(comparisons),
        # Backward-compatible legacy comparison fields.
        "total_agreed_weight_kg": 0.0,
        "total_agreed_weight": 0.0,
        "variance_kg": float(rounded(total_weight)),
        "collection_efficiency_percent": 0.0,
        "coverage_efficiency_percent": float(percent(total_points, total_trips)),
        "report_status": "Collected",
    }

    return {
        "source": source,
        "count": len(rows),
        "results": _paginate(rows, page, limit),
        ("monthly_trends" if monthly else "date_trends"): trend_rows,
        "panchayat_comparison": comparison_rows,
        "location_comparison": comparison_rows,
        "waste_type_breakdown": breakdown_rows,
        "kpis": kpis,
    }
