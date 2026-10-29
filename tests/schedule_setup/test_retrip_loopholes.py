"""Re-Trip loophole regressions — one block per scenario.

1. A Pending request left behind after the trip was closed another way must
   not be approvable into a second continuation.
2. Only one Pending request per trip, checked under the trip's row lock.
3. The role-level `edit` grant must not reach another company's requests.
4. Stops left out of a partial approval are marked Missed, not stranded.
5. A request still undecided when the trip's day ends lapses, and a
   continuation nobody started on its day is cancelled by the closer.
6. A trip that never started cannot be cut short.
7. Driver writes are refused on a closed trip or a carried-over stop.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.masters.waste_masters.bins import Bins
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.services import retrip_service
from app.services.stale_trip_closer import CONTINUATION_STOP_REASON, close_stale_trips
from app.viewsets.core_modules.daily_operations.trip_retrip_viewset import TripRetripRequestViewSet
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    lock_stop_for_write,
    raise_if_stop_unwritable,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def trip(bin_plan, collection_point, waste_type_obj):
    def _bin(sequence):
        return Bins.objects.create(
            company_id=bin_plan.company_id, project_id=bin_plan.project_id,
            district_id=bin_plan.district_id, city_id=bin_plan.city_id,
            collection_point_id=collection_point.unique_id,
            wastetype_id=waste_type_obj.unique_id, bin_capacity=100, bin_type="small",
            bin_name=f"Bin {sequence}", bin_image="", bin_qr="",
        )

    def create(*, stops=3, status=DailyTripAssignment.STATUS_IN_PROGRESS, days_ago=0):
        assignment = DailyTripAssignment.objects.create(
            trip_plan_id=bin_plan.unique_id, staff_template_id=bin_plan.staff_template_id,
            company_id=bin_plan.company_id, project_id=bin_plan.project_id,
            vehicle_id=bin_plan.vehicle_id,
            trip_date=timezone.localdate() - timedelta(days=days_ago),
            scheduled_time=bin_plan.scheduled_time, status=status,
            approval_status="Approved", waste_type_ids=bin_plan.waste_type_ids,
        )
        for sequence in range(1, stops + 1):
            DailyTripCollectionPoint.objects.create(
                trip_assignment_id=assignment.unique_id,
                collection_point_id=collection_point.unique_id,
                bin_id=_bin(sequence).unique_id, sequence=sequence,
                status=DailyTripCollectionPoint.STATUS_PENDING,
                company_id=assignment.company_id, project_id=assignment.project_id,
            )
        return assignment
    return create


def _stops(assignment):
    return list(
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment.unique_id
        ).order_by("sequence")
    )


def _continuations(source):
    return DailyTripAssignment.objects.filter(
        trip_plan_id=source.trip_plan_id, trip_date=source.trip_date
    ).exclude(unique_id=source.unique_id)


def _post(view_action, user, unique_id, data=None, permissions=None):
    request = APIRequestFactory().post(
        f"/retrip-requests/{unique_id}/{view_action}/", data or {}, format="json"
    )
    request.resolved_permissions = permissions or {}
    force_authenticate(request, user=user)
    return TripRetripRequestViewSet.as_view({"post": view_action})(request, unique_id=unique_id)


# ── 1. stale pending request cannot duplicate the continuation ──────────

def test_proceed_next_trip_decides_the_drivers_pending_request(trip, driver, supervisor):
    source = trip()
    driver_request = retrip_service.request_retrip(source, requested_by=driver, reason="Truck full")

    request, continuation = retrip_service.proceed_to_next_trip(
        source, actor=supervisor, collection_point_ids=None, remarks="Going to weighment",
    )

    assert request.pk == driver_request.pk
    assert TripRetripRequest.objects.count() == 1
    driver_request.refresh_from_db()
    assert driver_request.status == TripRetripRequest.STATUS_APPROVED
    assert driver_request.new_assignment_id == continuation.unique_id


def test_leftover_pending_request_on_closed_trip_cannot_be_approved(trip, driver, supervisor):
    source = trip()
    retrip_service.proceed_to_next_trip(
        source, actor=supervisor, collection_point_ids=None, remarks="Truck full",
    )
    # A Pending row left over from before the fix (or written around the service).
    stale = TripRetripRequest.objects.create(
        company_id=source.company_id, project_id=source.project_id,
        assignment_id=source.unique_id, reason="Old request",
        expires_at=timezone.now() + timedelta(minutes=30),
    )

    with pytest.raises(retrip_service.RetripRequestUnavailable):
        retrip_service.approve_retrip(stale, reviewed_by=supervisor)
    assert _continuations(source).count() == 1


def test_carried_stops_no_longer_count_as_pending_on_the_source(trip, driver, supervisor):
    source = trip()
    retrip_service.proceed_to_next_trip(
        source, actor=supervisor, collection_point_ids=None, remarks="Truck full",
    )
    source.refresh_from_db()
    assert all(stop.status == "Pending" and stop.carried_to_assignment for stop in _stops(source))
    assert not source.pending_bin_stops().exists()


def test_breakdown_continuation_supersedes_pending_request(trip, driver, supervisor):
    source = trip()
    pending = retrip_service.request_retrip(source, requested_by=driver, reason="Truck full")

    continuation = retrip_service.create_breakdown_continuation(
        source, vehicle_id=source.vehicle_id, alt_staff_template_id=None,
    )

    pending.refresh_from_db()
    assert pending.status == TripRetripRequest.STATUS_REJECTED
    assert continuation.unique_id in pending.review_remarks
    with pytest.raises(retrip_service.RetripRequestUnavailable):
        retrip_service.approve_retrip(pending, reviewed_by=supervisor)


# ── 2. one pending request per trip ─────────────────────────────────────

def test_second_request_on_same_trip_is_refused_by_the_service(trip, driver):
    source = trip()
    first = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")

    with pytest.raises(retrip_service.RetripAlreadyPending) as exc:
        retrip_service.request_retrip(source, requested_by=driver, reason="Full again")

    assert exc.value.request.pk == first.pk
    assert TripRetripRequest.objects.count() == 1


def test_new_request_allowed_once_previous_one_expired(trip, driver):
    source = trip()
    first = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")
    TripRetripRequest.objects.filter(pk=first.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    second = retrip_service.request_retrip(source, requested_by=driver, reason="Full again")

    first.refresh_from_db()
    assert first.status == TripRetripRequest.STATUS_EXPIRED
    assert second.is_pending


# ── 3. cross-company approval ───────────────────────────────────────────

EDIT_GRANT = {"schedule-operations": {"retrip-requests": ["view", "edit"]}}


def test_edit_grant_in_another_company_cannot_approve(trip, driver):
    from app.models.superadmin_masters.company import Company
    from app.models.superadmin_masters.project import Project

    other_company = Company.objects.create(name="Other Co", description="x")
    other_project = Project.objects.create(name="Other Project", company_id=other_company.unique_id)
    outsider = Staffcreation.objects.create(
        employee_name="Other Admin",
        company_id=other_company.unique_id, project_id=other_project.unique_id,
    )
    source = trip()
    request = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")

    response = _post("approve", outsider, request.unique_id, permissions=EDIT_GRANT)

    assert response.status_code == 403, response.data
    request.refresh_from_db()
    assert request.is_pending
    assert not _continuations(source).exists()


def test_edit_grant_in_same_company_can_approve(trip, driver, company, project):
    admin = Staffcreation.objects.create(
        employee_name="Same Co Admin", company_id=company.unique_id, project_id=project.unique_id,
    )
    source = trip()
    request = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")

    response = _post("approve", admin, request.unique_id, permissions=EDIT_GRANT)

    assert response.status_code == 200, response.data


def test_plan_supervisor_without_edit_grant_can_still_approve(trip, driver, supervisor):
    source = trip()
    request = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")

    response = _post("approve", supervisor, request.unique_id)

    assert response.status_code == 200, response.data


# ── 4. unselected stops are closed, not stranded ────────────────────────

def test_unselected_stops_are_marked_missed_on_partial_approval(trip, driver, supervisor):
    source = trip(stops=3)
    first, second, third = _stops(source)
    request = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")

    continuation = retrip_service.approve_retrip(
        request, reviewed_by=supervisor,
        collection_point_ids=[first.unique_id, third.unique_id],
    )

    second.refresh_from_db()
    assert second.status == DailyTripCollectionPoint.STATUS_MISSED
    assert request.unique_id in second.status_reason
    assert not second.carried_to_assignment
    assert len(_stops(continuation)) == 2


def test_full_approval_marks_nothing_missed(trip, driver, supervisor):
    source = trip(stops=2)
    request = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")

    retrip_service.approve_retrip(request, reviewed_by=supervisor)

    assert all(stop.status == "Pending" for stop in _stops(source))


# ── 5. day rollover ─────────────────────────────────────────────────────

def test_request_lapses_when_the_trip_day_has_ended(trip, driver, supervisor):
    source = trip(days_ago=1)
    request = retrip_service.request_retrip(source, requested_by=driver, reason="Vehicle full")

    assert retrip_service.approve_retrip(request, reviewed_by=supervisor) is None

    request.refresh_from_db()
    assert request.status == TripRetripRequest.STATUS_EXPIRED
    assert "day ended" in request.review_remarks
    assert not _continuations(source).exists()


def test_proceed_next_trip_refuses_a_past_day(trip, supervisor):
    source = trip(days_ago=1)

    with pytest.raises(ValueError, match="day has ended"):
        retrip_service.proceed_to_next_trip(
            source, actor=supervisor, collection_point_ids=None, remarks="Vehicle full",
        )
    assert not _continuations(source).exists()


def test_closer_cancels_continuation_never_started_on_its_day(trip, driver, supervisor):
    source = trip(stops=2)
    _request, continuation = retrip_service.proceed_to_next_trip(
        source, actor=supervisor, collection_point_ids=None, remarks="Vehicle full",
    )
    yesterday = timezone.localdate() - timedelta(days=1)
    DailyTripAssignment.objects.filter(
        unique_id__in=[source.unique_id, continuation.unique_id]
    ).update(trip_date=yesterday)

    result = close_stale_trips()

    assert result["cancelled_continuations"] == [continuation.unique_id]
    continuation.refresh_from_db()
    assert continuation.status == DailyTripAssignment.STATUS_CANCELLED
    assert all(
        stop.status == DailyTripCollectionPoint.STATUS_MISSED
        and stop.status_reason == CONTINUATION_STOP_REASON
        for stop in _stops(continuation)
    )


def test_closer_leaves_ordinary_scheduled_trips_alone(trip):
    ordinary = trip(status=DailyTripAssignment.STATUS_SCHEDULED, days_ago=1)

    result = close_stale_trips()

    assert result["cancelled_continuations"] == []
    ordinary.refresh_from_db()
    assert ordinary.status == DailyTripAssignment.STATUS_SCHEDULED


# ── 6. trip that never started ──────────────────────────────────────────

def test_request_refused_for_trip_that_never_started(trip, driver):
    source = trip(status=DailyTripAssignment.STATUS_SCHEDULED)

    with pytest.raises(retrip_service.RetripNotAllowed):
        retrip_service.request_retrip(source, requested_by=driver, reason="Skipping this trip entirely")
    assert not TripRetripRequest.objects.exists()


def test_web_create_refuses_trip_that_never_started(trip, supervisor):
    source = trip(status=DailyTripAssignment.STATUS_SCHEDULED)
    request = APIRequestFactory().post(
        "/retrip-requests/", {"assignment_id": source.unique_id, "reason": "Skipping this trip entirely"}, format="json"
    )
    force_authenticate(request, user=supervisor)

    response = TripRetripRequestViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 400, response.data
    assert not TripRetripRequest.objects.exists()


# ── 7. driver writes after approval ─────────────────────────────────────

def test_carried_stop_on_source_is_not_writable(trip, driver, supervisor):
    source = trip(stops=1)
    retrip_service.proceed_to_next_trip(
        source, actor=supervisor, collection_point_ids=None, remarks="Vehicle full",
    )
    source.refresh_from_db()
    (stop,) = _stops(source)

    with pytest.raises(OperatorFlowError) as exc:
        lock_stop_for_write(source, stop)
    assert exc.value.code == "TRIP_CLOSED"

    # Even if the trip were somehow still open, the carried stop is not its own.
    source.status = DailyTripAssignment.STATUS_IN_PROGRESS
    with pytest.raises(OperatorFlowError) as exc:
        raise_if_stop_unwritable(source, stop)
    assert exc.value.code == "STOP_CARRIED_OVER"


def test_stop_collected_meanwhile_is_refused_by_the_lock_recheck(trip):
    source = trip(stops=1)
    (stop,) = _stops(source)
    # Another request collected it after this one validated the stop.
    DailyTripCollectionPoint.objects.filter(pk=stop.pk).update(
        is_collected=True, status=DailyTripCollectionPoint.STATUS_COLLECTED
    )

    with pytest.raises(OperatorFlowError) as exc:
        lock_stop_for_write(source, stop)
    assert exc.value.code == "ALREADY_COLLECTED"


def test_open_trip_stop_is_writable(trip):
    source = trip(stops=1)
    (stop,) = _stops(source)

    assert lock_stop_for_write(source, stop).pk == stop.pk
