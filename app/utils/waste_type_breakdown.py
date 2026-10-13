"""Bulk waste-type aggregation for waste collection reports.

The report KPIs are calculated from ``DailyTripLog``.  This module is kept
separate because joining collection detail rows directly to that queryset
would count one trip once for every waste type it contains.
"""
from decimal import Decimal

from django.db.models import OuterRef, Subquery, Sum


HOUSEHOLD_WASTE_TYPE_NAMES = {
    "wet_waste": "Wet Waste",
    "dry_waste": "Dry Waste",
    "mixed_waste": "Mixed Waste",
}
HOUSEHOLD_WASTE_TYPE_FALLBACK_ID_PREFIX = "HOUSEHOLD"


def _daily_trip_log_fields():
    from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
    return {
        "trip_date": Subquery(
            DailyTripLog.objects.filter(
                trip_assignment_id=OuterRef("trip_assignment_id")
            ).values("trip_date")[:1]
        ),
        "log_status": Subquery(
            DailyTripLog.objects.filter(
                trip_assignment_id=OuterRef("trip_assignment_id")
            ).values("log_status")[:1]
        ),
    }


def _waste_type_name_field():
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
    return Subquery(
        WasteType.objects.filter(
            unique_id=OuterRef("waste_type_id")
        ).values("waste_type_name")[:1]
    )


def bulk_waste_type_rows_for_trip_assignments(
    trip_assignment_ids, source="bin", extra_group_by=(),
):
    """Return non-zero per-assignment/per-waste-type weights in bulk."""
    from app.models.core_modules.daily_operations.wastecollection import WasteCollection
    from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType

    assignment_ids = list(trip_assignment_ids)
    if not assignment_ids:
        return []

    # DailyTripLog fields the caller asked to see on every returned row
    # (e.g. "trip_date", to cross-check against its own copy) — resolved
    # once per assignment_id so both the bin/all branch (which already
    # annotates them per BinCollectionEvent row) and the household branch
    # (WasteCollection has no such annotation of its own) can populate them.
    daily_log_lookup = {}
    if extra_group_by:
        from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
        daily_log_lookup = {
            row["trip_assignment_id"]: row
            for row in DailyTripLog.objects.filter(
                trip_assignment_id__in=assignment_ids
            ).values("trip_assignment_id", *extra_group_by)
        }

    rows_by_key = {}

    def add(assignment_id, extra_values, waste_type_id, waste_type_name, weight):
        if not weight:
            return
        key = (assignment_id, *extra_values, waste_type_id)
        if key not in rows_by_key:
            rows_by_key[key] = {
                "trip_assignment_id": assignment_id,
                **dict(zip(extra_group_by, extra_values)),
                "waste_type_id": waste_type_id,
                "waste_type_name": waste_type_name,
                "weight_kg": Decimal("0"),
            }
        rows_by_key[key]["weight_kg"] += Decimal(str(weight))

    if source in ("bin", "all"):
        daily_log_fields = _daily_trip_log_fields()
        group_fields = [
            "trip_assignment_id",
            *list(daily_log_fields.keys()),
            "waste_type_id",
            "waste_type_name",
        ]
        rows = (
            BinCollectionEvent.objects.filter(
                trip_assignment_id__in=assignment_ids,
                is_deleted=False,
            )
            .annotate(
                waste_type_name=_waste_type_name_field(),
                **{k: v for k, v in daily_log_fields.items()},
            )
            .values(*group_fields)
            .annotate(total_weight=Sum("collected_weight_kg"))
        )
        for row in rows:
            extra_values = tuple(
                row.get(field) for field in daily_log_fields
            )
            add(
                row["trip_assignment_id"],
                extra_values,
                row["waste_type_id"],
                row["waste_type_name"] or row["waste_type_id"],
                row["total_weight"],
            )

    if source in ("household", "all"):
        group_fields = [
            "trip_assignment_id",
        ]
        rows = (
            WasteCollection.objects.filter(
                trip_assignment_id__in=assignment_ids,
                is_deleted=False,
            )
            .values(*group_fields)
            .annotate(**{
                field: Sum(field) for field in HOUSEHOLD_WASTE_TYPE_NAMES
            })
        )
        masters = {
            item.waste_type_name: item
            for item in WasteType.objects.filter(is_deleted=False)
        }
        for row in rows:
            log_row = daily_log_lookup.get(row["trip_assignment_id"], {})
            extra_values = tuple(log_row.get(field) for field in extra_group_by)
            for field, label in HOUSEHOLD_WASTE_TYPE_NAMES.items():
                weight = row.get(field)
                if not weight:
                    continue
                master = masters.get(label)
                add(
                    row["trip_assignment_id"],
                    extra_values,
                    master.unique_id if master else f"{HOUSEHOLD_WASTE_TYPE_FALLBACK_ID_PREFIX}-{field}",
                    master.waste_type_name if master else label,
                    weight,
                )

    return list(rows_by_key.values())
