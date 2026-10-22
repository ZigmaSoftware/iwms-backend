from datetime import timedelta

import pytest
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.trip_retrip_request import (
    TripRetripRequest,
)
from app.services.stale_trip_closer import STOP_REASON, close_stale_trips


def _trip(company, project, *, days_ago, status="In Progress"):
    return DailyTripAssignment.objects.create(
        trip_date=timezone.localdate() - timedelta(days=days_ago),
        status=status,
        scheduled_time="07:00",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )


def _bin_stop(trip, company, project, status, seq):
    return DailyTripCollectionPoint.objects.create(
        trip_assignment_id=trip.unique_id,
        sequence=seq,
        status=status,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )


@pytest.mark.django_db
def test_closes_past_in_progress_trip_and_marks_unresolved_stops_missed(
    company, project
):
    trip = _trip(company, project, days_ago=1)
    done = _bin_stop(trip, company, project, DailyTripCollectionPoint.STATUS_COLLECTED, 1)
    pending = _bin_stop(trip, company, project, DailyTripCollectionPoint.STATUS_PENDING, 2)
    later = _bin_stop(trip, company, project, DailyTripCollectionPoint.STATUS_SKIPPED, 3)

    result = close_stale_trips()

    assert result["closed"] == [trip.unique_id]
    assert result["stops_marked_missed"] == 2
    trip.refresh_from_db()
    assert trip.status == DailyTripAssignment.STATUS_COMPLETED
    assert "Closed automatically by the system" in trip.remarks
    assert trip.actual_end_at is not None
    assert trip.actual_end_at.date() == trip.trip_date
    done.refresh_from_db()
    pending.refresh_from_db()
    later.refresh_from_db()
    assert done.status == DailyTripCollectionPoint.STATUS_COLLECTED
    for stop in (pending, later):
        assert stop.status == DailyTripCollectionPoint.STATUS_MISSED
        assert stop.status_reason == STOP_REASON


@pytest.mark.django_db
def test_household_stops_become_not_available(company, project):
    trip = _trip(company, project, days_ago=2)
    stop = DailyTripHouseholdCollection.objects.create(
        trip_assignment_id=trip.unique_id,
        customer_id="CUST-1",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    close_stale_trips()
    stop.refresh_from_db()
    assert stop.status == DailyTripHouseholdCollection.STATUS_MISSED
    assert stop.is_collected is False


@pytest.mark.django_db
def test_leaves_today_scheduled_and_completed_trips_alone(company, project):
    today = _trip(company, project, days_ago=0)
    scheduled = _trip(company, project, days_ago=1, status="Scheduled")
    completed = _trip(company, project, days_ago=1, status="Completed")

    result = close_stale_trips()

    assert result["closed"] == []
    today.refresh_from_db()
    scheduled.refresh_from_db()
    completed.refresh_from_db()
    assert today.status == "In Progress"
    assert scheduled.status == "Scheduled"
    assert completed.remarks in (None, "")


@pytest.mark.django_db
def test_expires_leftover_retrip_request_then_closes_trip(company, project):
    """A request still Pending on a past day (the timeout cron never ran)
    must not keep the trip open forever: its window ended with the day."""
    trip = _trip(company, project, days_ago=1)
    _bin_stop(trip, company, project, DailyTripCollectionPoint.STATUS_PENDING, 1)
    request = TripRetripRequest.objects.create(
        assignment_id=trip.unique_id,
        reason="Vehicle full",
        status=TripRetripRequest.STATUS_PENDING,
        company_id=company.unique_id,
        project_id=project.unique_id,
        expires_at=timezone.now() + timedelta(minutes=30),
    )

    result = close_stale_trips()

    assert result["skipped_pending_decision"] == []
    assert result["closed"] == [trip.unique_id]
    request.refresh_from_db()
    assert request.status == TripRetripRequest.STATUS_EXPIRED
    trip.refresh_from_db()
    assert trip.status == "Completed"


@pytest.mark.django_db
def test_is_idempotent(company, project):
    trip = _trip(company, project, days_ago=1)
    _bin_stop(trip, company, project, DailyTripCollectionPoint.STATUS_PENDING, 1)
    close_stale_trips()
    second = close_stale_trips()
    assert second["closed"] == []
    trip.refresh_from_db()
    assert trip.remarks.count("Closed automatically") == 1
