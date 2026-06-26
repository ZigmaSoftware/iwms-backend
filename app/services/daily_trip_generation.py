from django.db import transaction

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint


def should_generate_for_date(plan: TripPlan, target_date, force: bool = False) -> bool:
    if force:
        return True
    repeat_days = plan.repeat_days or []
    if not repeat_days:
        return True
    try:
        allowed_days = {int(day) for day in repeat_days}
    except (TypeError, ValueError):
        return False
    return target_date.weekday() in allowed_days


def active_auto_assign_plans(force: bool = False):
    queryset = TripPlan.objects.filter(
        is_deleted=False,
        status=TripPlan.Status.ACTIVE,
    )
    if not force:
        queryset = queryset.filter(
            approval_status=TripPlan.ApprovalStatus.APPROVED,
        )
    return queryset.select_related("company_id", "project_id")


def ensure_assignment_collection_points(assignment: DailyTripAssignment, created_by=None) -> int:
    if not assignment or not assignment.trip_plan_id_id:
        return 0

    existing_stop_keys = set(
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment,
            is_deleted=False,
        ).values_list("collection_point_id_id", "bin_id_id")
    )
    stops = (
        TripPlanCollectionPoint.objects.filter(
            trip_plan_id=assignment.trip_plan_id,
            collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
            is_active=True,
            is_deleted=False,
        )
        .exclude(collection_point_id__isnull=True)
        .exclude(bin_id__isnull=True)
        .select_related("collection_point_id", "bin_id")
        .order_by("sequence")
    )

    created_count = 0
    for stop in stops:
        stop_key = (stop.collection_point_id_id, stop.bin_id_id)
        if stop_key in existing_stop_keys:
            continue
        DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment,
            collection_point_id=stop.collection_point_id,
            bin_id=stop.bin_id,
            sequence=stop.sequence,
            is_collected=False,
            status=DailyTripCollectionPoint.STATUS_PENDING,
            created_by=created_by,
        )
        existing_stop_keys.add(stop_key)
        created_count += 1
    return created_count


@transaction.atomic
def generate_assignment_for_plan(plan: TripPlan, target_date, created_by=None):
    defaults = {
        "staff_template_id": plan.staff_template_id,
        "vehicle_id": plan.vehicle_id,
        "waste_type_ids": plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else []),
        "panchayat_id": plan.panchayat_id,
        "ward_id": plan.ward_id,
        "scheduled_time": plan.scheduled_time,
    }
    assignment, created = DailyTripAssignment.objects.get_or_create(
        company_id=plan.company_id,
        project_id=plan.project_id,
        trip_plan_id=plan,
        trip_date=target_date,
        defaults=defaults,
    )
    if not created:
        update_fields = []
        if not assignment.waste_type_ids:
            assignment.waste_type_ids = plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else [])
            update_fields.append("waste_type_ids")
        if update_fields:
            assignment.save(update_fields=update_fields)
    signal_created_count = 0
    if created:
        signal_created_count = DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment,
            is_deleted=False,
        ).count()
    cp_created = signal_created_count + ensure_assignment_collection_points(
        assignment,
        created_by=created_by,
    )
    return assignment, created, cp_created


def generate_daily_trips_for_date(target_date, force: bool = False):
    created_count = 0
    skipped_count = 0
    existing_count = 0
    point_count = 0
    errors = []

    for plan in active_auto_assign_plans(force=force):
        if not should_generate_for_date(plan, target_date, force=force):
            skipped_count += 1
            continue
        try:
            _assignment, created, cp_created = generate_assignment_for_plan(plan, target_date)
        except Exception as exc:
            errors.append((plan.unique_id, str(exc)))
            continue
        if created:
            created_count += 1
        else:
            existing_count += 1
        point_count += cp_created

    return {
        "assignments_created": created_count,
        "assignments_existing": existing_count,
        "collection_points_created": point_count,
        "skipped": skipped_count,
        "errors": errors,
    }
