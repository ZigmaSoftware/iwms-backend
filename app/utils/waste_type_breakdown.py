"""Bulk waste-type aggregation for waste collection reports.

The report KPIs are calculated from ``DailyTripLog``.  This module is kept
separate because joining collection detail rows directly to that queryset
would count one trip once for every waste type it contains.
"""
from decimal import Decimal

from django.db.models import Sum


HOUSEHOLD_WASTE_TYPE_NAMES = {
    "wet_waste": "Wet Waste",
    "dry_waste": "Dry Waste",
    "mixed_waste": "Mixed Waste",
}
HOUSEHOLD_WASTE_TYPE_FALLBACK_ID_PREFIX = "HOUSEHOLD"


def bulk_waste_type_rows_for_trip_assignments(
    trip_assignment_ids, source="bin", extra_group_by=(),
):
    """Return non-zero per-assignment/per-waste-type weights in bulk."""
    from app.models.customers.wastecollection import WasteCollection
    from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
    from app.models.staff_creations.waste_collection_bluetooth import WasteType

    assignment_ids = list(trip_assignment_ids)
    if not assignment_ids:
        return []

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
        group_fields = [
            "trip_assignment_id",
            *(f"trip_assignment_id__daily_trip_log__{field}" for field in extra_group_by),
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ]
        rows = (
            BinCollectionEvent.objects.filter(
                trip_assignment_id__in=assignment_ids,
                is_deleted=False,
            )
            .values(*group_fields)
            .annotate(total_weight=Sum("collected_weight_kg"))
        )
        for row in rows:
            extra_values = tuple(
                row[f"trip_assignment_id__daily_trip_log__{field}"]
                for field in extra_group_by
            )
            add(
                row["trip_assignment_id"],
                extra_values,
                row["waste_type_id"],
                row["waste_type_id__waste_type_name"] or row["waste_type_id"],
                row["total_weight"],
            )

    if source in ("household", "all"):
        group_fields = [
            "trip_assignment_id",
            *(f"trip_assignment_id__daily_trip_log__{field}" for field in extra_group_by),
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
            extra_values = tuple(
                row[f"trip_assignment_id__daily_trip_log__{field}"]
                for field in extra_group_by
            )
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
