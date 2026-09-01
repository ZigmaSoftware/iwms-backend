from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)

# Most specific level first: a stop/trip plan scoped to a single Panchayat
# should only match customers in that exact Panchayat. Mirrors TN_Iwms'
# _GEO_MATCH_FIELDS, adapted to IWMS's flat geo field names (zone/ward/
# panchayat rather than TN's full district/corporation/municipality tree).
_GEO_MATCH_FIELDS = (
    "panchayat",
    "zone",
    "ward",
)


def _raw_fk_value(obj, field):
    """Return the raw FK value for IWMS's mixed FK naming styles.

    Some models use `zone = ForeignKey(...)` (raw value at `zone_id`), while
    others use `zone_id = ForeignKey(...)` (raw value at `zone_id_id`).
    """
    for attr in (f"{field}_id_id", f"{field}_id", field):
        if not hasattr(obj, attr):
            continue
        value = getattr(obj, attr, None)
        if value:
            return getattr(value, "pk", value)
    return None


def _geo_filter_for(obj):
    """The exact (field, value) filter matching CustomerCreation rows scoped
    to precisely `obj`'s most specific populated geo field (e.g. a stop
    scoped to a Panchayat only matches customers whose `panchayat` FK equals
    that panchayat). Returns None if `obj` has no geo field populated."""
    if not obj:
        return None
    for field in _GEO_MATCH_FIELDS:
        value = _raw_fk_value(obj, field)
        if value:
            # CustomerCreation exposes "zone"/"ward" as plain FK fields, so
            # the matching lookup on the queryset is "<field>_id".
            return f"{field}_id", value
    return None


def _customers_for_household_stop(stop, wards=None):
    from app.models.customers.customercreation import CustomerCreation

    is_bulk_stop = stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BULK

    if stop.customer_id_id:
        return CustomerCreation.objects.filter(
            unique_id=stop.customer_id_id,
            is_deleted=False,
            is_bulkwaste_generator=is_bulk_stop,
        )

    geo_filter = _geo_filter_for(stop) or _geo_filter_for(stop.trip_plan_id)
    if not geo_filter:
        ward_ids = list(wards.values_list("unique_id", flat=True)) if wards is not None else []
        if ward_ids:
            return CustomerCreation.objects.filter(
                is_deleted=False,
                is_active=True,
                is_bulkwaste_generator=is_bulk_stop,
                ward_id__in=ward_ids,
            )
        return CustomerCreation.objects.none()

    field, value = geo_filter
    queryset = CustomerCreation.objects.filter(
        is_deleted=False,
        is_active=True,
        is_bulkwaste_generator=is_bulk_stop,
        **{field: value},
    )
    ward_ids = list(wards.values_list("unique_id", flat=True)) if wards is not None else []
    if ward_ids:
        queryset = queryset.filter(ward_id__in=ward_ids)
    return queryset


def _create_daily_household_collections(assignment, stop):
    from app.models.schedule_masters.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )

    collection_type = (
        DailyTripHouseholdCollection.COLLECTION_TYPE_BULK
        if stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BULK
        else DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD
    )
    created_count = 0
    for offset, customer in enumerate(_customers_for_household_stop(stop, wards=assignment.wards), start=0):
        _, created = DailyTripHouseholdCollection.objects.get_or_create(
            trip_assignment_id=assignment,
            customer_id=customer,
            collection_type=collection_type,
            defaults={
                "sequence": stop.sequence + offset,
                "is_collected": False,
                "status": DailyTripHouseholdCollection.STATUS_PENDING,
            },
        )
        if created:
            created_count += 1
    return created_count


def sync_daily_assignment_stops_from_plan(assignment):
    """Clone the assignment's Trip Plan stops into its daily child tables.

    Uses get_or_create throughout, so it is safe to call repeatedly: it adds
    stops that aren't cloned yet (e.g. stops added to the plan after the
    assignment was first created) and only removes pending household rows that
    fall outside the selected wards. Collected data is never overwritten.
    Returns the number of new rows.

    This is the single authoritative "clone stops" code path for IWMS —
    invoked both by the post_save signal below (fires the moment a
    DailyTripAssignment is created) and by `run_for_date`
    (management command / manual API run / nightly scheduler, see
    app/management/commands/generate_daily_trips.py) as a safety net. Both
    callers use get_or_create, so nothing is ever duplicated no matter which
    path wins the race — mirrors TN_Iwms' design exactly.
    """
    if not assignment.trip_plan_id_id:
        return 0

    plan = assignment.trip_plan_id
    plan_stops = TripPlanCollectionPoint.objects.filter(
        trip_plan_id=plan,
        collection_type=plan.collection_type,
        is_active=True,
        is_deleted=False,
    ).order_by("sequence")

    from app.models.schedule_masters.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )

    selected_ward_ids = list(assignment.wards.values_list("unique_id", flat=True))
    if selected_ward_ids:
        DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=assignment,
            is_collected=False,
            is_deleted=False,
        ).exclude(customer_id__ward_id__in=selected_ward_ids).delete()

    added = 0
    for stop in plan_stops:
        if stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
            if not stop.collection_point_id_id or not stop.bin_id_id:
                continue
            _, created = DailyTripCollectionPoint.objects.get_or_create(
                trip_assignment_id=assignment,
                collection_point_id=stop.collection_point_id,
                bin_id=stop.bin_id,
                defaults={
                    "sequence": stop.sequence,
                    "is_collected": False,
                    "status": DailyTripCollectionPoint.STATUS_PENDING,
                    "created_by": getattr(assignment, "created_by", None),
                },
            )
            if created:
                added += 1

        elif stop.collection_type in {
            TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
            TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
        }:
            added += _create_daily_household_collections(assignment, stop)

    return added


@receiver(post_save, sender=DailyTripAssignment)
def copy_trip_plan_stops_to_daily_assignment(sender, instance, created, **kwargs):
    if not created:
        return
    sync_daily_assignment_stops_from_plan(instance)


@receiver(post_save, sender="app.WasteCollection")
def sync_household_collection_on_waste_save(sender, instance, **kwargs):
    """When a WasteCollection is saved with a trip_assignment_id:
    1. Find or create the DailyTripHouseholdCollection entry for that customer + trip.
    2. Mark it collected with the recorded weight.
    3. Find or create the DailyTripLog for the trip.
    4. Sync household_collected_weight_kg on the log.
    5. Auto-complete the trip assignment once every household stop is
       resolved (Collected or Not Available) — see
       `DailyTripAssignment.mark_completed_if_all_household_stops_collected`.
       This step was documented here but never implemented: a household trip
       could show every stop Collected on the driver's list while the
       assignment itself stayed "In Progress" forever, because the only
       completion check that existed (`mark_completed_if_all_cps_collected`)
       looks at bin stops, which a household trip has none of.
    """
    if not instance.trip_assignment_id_id or instance.is_deleted:
        return

    from app.models.schedule_masters.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )
    from app.models.schedule_masters.daily_trip_log import DailyTripLog

    collection_type = (
        DailyTripHouseholdCollection.COLLECTION_TYPE_BULK
        if getattr(instance.customer, "is_bulkwaste_generator", False)
        else DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD
    )

    # 1. Update / create the household collection entry
    dthc, _ = DailyTripHouseholdCollection.objects.get_or_create(
        trip_assignment_id=instance.trip_assignment_id,
        customer_id=instance.customer,
        collection_type=collection_type,
        defaults={"status": DailyTripHouseholdCollection.STATUS_PENDING},
    )
    dthc.mark_collected(instance)

    # 2. Find or auto-create the trip log
    log = DailyTripLog.objects.filter(
        trip_assignment_id=instance.trip_assignment_id_id,
        is_deleted=False,
    ).first()

    if log is None:
        try:
            log = DailyTripLog(
                trip_assignment_id=instance.trip_assignment_id,
                remarks="Auto-generated from household waste collections.",
            )
            # autofill_from_assignment() is called inside save()
            log.save()
        except Exception:
            # If assignment is missing required fields (no staff template,
            # vehicle, etc.) skip log creation gracefully.
            return

    # 3. Sync household weight onto the log
    log.sync_from_household_collections()

    # 4. Driver app write path — ending the trip is now a driver-confirmed
    # action (see TripCompletionNudge on the app side) rather than an
    # automatic side effect of the last WasteCollection save.
    instance.trip_assignment_id.mark_completed_if_all_household_stops_collected(
        auto_end=False
    )


@receiver(post_save, sender="app.BinCollectionEvent")
def sync_bin_collection_on_event_save(sender, instance, **kwargs):
    """Mirrors sync_household_collection_on_waste_save for the bin-collection
    side: when a BinCollectionEvent (secondary/bin scan) is saved, find or
    create the trip's DailyTripLog and sync collected_weight_kg from all
    BinCollectionEvent rows on that trip.

    Without this, bin-collection trips never produced a DailyTripLog through
    normal app usage — only household collections had an equivalent signal —
    so panchayat-based reports (Daily/Monthly Waste Comparison) never saw bin
    data unless something else (e.g. a seeder) manually created the log.
    """
    if not instance.trip_assignment_id_id or instance.is_deleted:
        return

    from app.models.schedule_masters.daily_trip_log import DailyTripLog

    log = DailyTripLog.objects.filter(
        trip_assignment_id=instance.trip_assignment_id_id,
        is_deleted=False,
    ).first()

    if log is None:
        try:
            log = DailyTripLog(
                trip_assignment_id=instance.trip_assignment_id,
                remarks="Auto-generated from bin collection events.",
            )
            # autofill_from_assignment() and sync_from_bin_collection_events()
            # are both called inside save().
            log.save()
            return
        except Exception:
            # If assignment is missing required fields (no staff template,
            # vehicle, etc.) skip log creation gracefully.
            return

    log.sync_from_bin_collection_events()
