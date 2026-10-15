from datetime import date

import pytest

from app.management.commands.generate_daily_trips import run_for_date
from app.models.core_modules.daily_operations.daily_service_notice import DailyServiceNotice
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.services.daily_service_notice import (
    DailyServiceNoticeError,
    declare_no_collection,
    notice_for_customer,
    revoke_no_collection,
)
from tests.schedule_setup.conftest import _make_plan


@pytest.mark.django_db
def test_notice_prevents_nightly_scheduler_from_recreating_trip(bin_stop):
    plan = bin_stop.trip_plan
    plan.repeat_days = [0, 1, 2, 3, 4, 5, 6]
    plan.save(update_fields=["repeat_days"])
    service_date = date(2026, 8, 3)

    declare_no_collection(
        plan,
        service_date,
        DailyServiceNotice.REASON_HOLIDAY,
        "",
    )
    summary = run_for_date(target_date=service_date)

    assert summary["created"] == 0
    assert not DailyTripAssignment.objects.filter(
        trip_plan_id=plan.unique_id, trip_date=service_date
    ).exists()


@pytest.mark.django_db
def test_notice_cancels_scheduled_assignment_but_preserves_it(bin_stop):
    plan = bin_stop.trip_plan
    service_date = date(2026, 8, 3)
    assignment = DailyTripAssignment.objects.create(
        trip_plan_id=plan.unique_id,
        trip_date=service_date,
        scheduled_time=plan.scheduled_time,
        status=DailyTripAssignment.STATUS_SCHEDULED,
        company_id=plan.company_id,
        project_id=plan.project_id,
    )

    declare_no_collection(
        plan,
        service_date,
        DailyServiceNotice.REASON_WEATHER,
        "Cyclone warning",
    )

    assignment.refresh_from_db()
    assert assignment.status == DailyTripAssignment.STATUS_CANCELLED
    assert "Cyclone warning" in assignment.remarks
    assert DailyServiceNotice.objects.filter(
        trip_plan_id=plan.unique_id, service_date=service_date
    ).count() == 1


@pytest.mark.django_db
def test_notice_rejected_after_trip_started(bin_stop):
    plan = bin_stop.trip_plan
    service_date = date(2026, 8, 3)
    DailyTripAssignment.objects.create(
        trip_plan_id=plan.unique_id,
        trip_date=service_date,
        scheduled_time=plan.scheduled_time,
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        company_id=plan.company_id,
        project_id=plan.project_id,
    )

    with pytest.raises(DailyServiceNoticeError, match="already started"):
        declare_no_collection(
            plan,
            service_date,
            DailyServiceNotice.REASON_STAFF_UNAVAILABLE,
            "",
        )


@pytest.mark.django_db
def test_household_notice_is_visible_to_affected_customer(
    company,
    project,
    district,
    city,
    panchayat,
    staff_template,
    vehicle,
    supervisor,
    waste_type_obj,
    household_customer,
):
    plan = _make_plan(
        company,
        project,
        district,
        city,
        panchayat,
        staff_template,
        vehicle,
        supervisor,
        waste_type_obj,
        collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
        repeat_days=[0, 1, 2, 3, 4, 5, 6],
    )
    TripPlanCollectionPoint.objects.create(
        trip_plan_id=plan.unique_id,
        collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
        customer_id=household_customer.unique_id,
        sequence=1,
        is_active=True,
    )
    service_date = date(2026, 8, 3)
    notice = declare_no_collection(
        plan,
        service_date,
        DailyServiceNotice.REASON_FLOOD,
        "Roads are inaccessible",
    )

    assert household_customer.unique_id in notice.recipient_customer_ids
    assert notice_for_customer(household_customer, service_date) == notice


@pytest.mark.django_db
def test_other_reason_requires_explanation(bin_stop):
    with pytest.raises(DailyServiceNoticeError, match="explanation"):
        declare_no_collection(
            bin_stop.trip_plan,
            date(2026, 8, 3),
            DailyServiceNotice.REASON_OTHER,
            "",
        )


@pytest.mark.django_db
def test_repeated_notice_is_idempotent(bin_stop):
    plan = bin_stop.trip_plan
    service_date = date(2026, 8, 3)
    first = declare_no_collection(
        plan,
        service_date,
        DailyServiceNotice.REASON_HOLIDAY,
        "",
    )
    second = declare_no_collection(
        plan,
        service_date,
        DailyServiceNotice.REASON_HOLIDAY,
        "",
    )
    assert first.unique_id == second.unique_id
    assert DailyServiceNotice.objects.filter(
        trip_plan_id=plan.unique_id, service_date=service_date
    ).count() == 1


@pytest.mark.django_db
def test_revoking_notice_restores_only_notice_cancelled_assignment(bin_stop):
    plan = bin_stop.trip_plan
    service_date = date(2026, 8, 3)
    assignment = DailyTripAssignment.objects.create(
        trip_plan_id=plan.unique_id,
        trip_date=service_date,
        scheduled_time=plan.scheduled_time,
        status=DailyTripAssignment.STATUS_SCHEDULED,
        company_id=plan.company_id,
        project_id=plan.project_id,
    )
    notice = declare_no_collection(
        plan,
        service_date,
        DailyServiceNotice.REASON_WEATHER,
        "Storm warning",
    )
    revoke_no_collection(notice, reason="Warning withdrawn")

    assignment.refresh_from_db()
    notice.refresh_from_db()
    assert notice.status == DailyServiceNotice.STATUS_REVOKED
    assert assignment.status == DailyTripAssignment.STATUS_SCHEDULED
    assert assignment.remarks == "Service restored: Warning withdrawn"
