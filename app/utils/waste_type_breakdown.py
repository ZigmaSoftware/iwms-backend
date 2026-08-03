from decimal import Decimal

from django.db.models import Sum

HOUSEHOLD_WASTE_TYPE_NAMES = {
    "wet_waste": "Wet Waste",
    "dry_waste": "Dry Waste",
    "mixed_waste": "Mixed Waste",
    "sanitary_waste": "Sanitary Waste",
}


def waste_type_breakdown_for_assignment(assignment):
    """Actual weight collected per waste type for one DailyTripAssignment,
    combining bin collection events (each carries its own waste type +
    weight) and household collections (wet/dry/mixed/sanitary columns,
    mapped to WasteType master names)."""
    from app.models.user_creations.waste_collection_bluetooth import WasteType
    from app.models.customers.wastecollection import WasteCollection
    from app.models.schedule_masters.bin_collection_event import BinCollectionEvent

    totals = {}

    bin_rows = (
        BinCollectionEvent.objects.filter(trip_assignment_id=assignment, is_deleted=False)
        .values("waste_type_id", "waste_type_id__waste_type_name")
        .annotate(total_weight=Sum("collected_weight_kg"))
    )
    for row in bin_rows:
        name = row["waste_type_id__waste_type_name"]
        if not name or not row["total_weight"]:
            continue
        totals[name] = totals.get(name, Decimal("0")) + row["total_weight"]

    household_rows = WasteCollection.objects.filter(
        trip_assignment_id=assignment, is_deleted=False
    ).aggregate(
        wet_waste=Sum("wet_waste"),
        dry_waste=Sum("dry_waste"),
        mixed_waste=Sum("mixed_waste"),
        sanitary_waste=Sum("sanitary_waste"),
    )
    waste_type_names = set(
        WasteType.objects.filter(is_deleted=False).values_list("waste_type_name", flat=True)
    )
    for column, label in HOUSEHOLD_WASTE_TYPE_NAMES.items():
        value = household_rows.get(column)
        if not value:
            continue
        name = label if label in waste_type_names else label
        totals[name] = totals.get(name, Decimal("0")) + Decimal(str(value))

    return [
        {"waste_type_name": name, "collected_weight_kg": totals[name]}
        for name in totals
    ]
