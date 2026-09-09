"""Supervisor list modes: service date, ownership, complete history and paging."""
from datetime import timedelta
from copy import copy

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.viewsets.core_modules.daily_operations.daily_trip_assignment_viewset import DailyTripAssignmentViewSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def assignment_factory(bin_plan):
    def create(day, status="Scheduled"):
        return DailyTripAssignment.objects.create(
            trip_plan_id=bin_plan, staff_template_id=bin_plan.staff_template_id,
            company_id=bin_plan.company_id, project_id=bin_plan.project_id,
            vehicle_id=bin_plan.vehicle_id, trip_date=day,
            scheduled_time=bin_plan.scheduled_time, status=status,
            approval_status="Approved", waste_type_ids=bin_plan.waste_type_ids,
        )
    return create


def get_list(user, **params):
    request = APIRequestFactory().get('/trips/', {'mine': 'true', **params})
    force_authenticate(request, user=user)
    return DailyTripAssignmentViewSet.as_view({'get': 'list'})(request)


def test_workbench_keeps_only_today_and_older_unfinished(assignment_factory, supervisor):
    today = timezone.localdate()
    old_running = assignment_factory(today - timedelta(days=12), 'In Progress')
    old_scheduled = assignment_factory(today - timedelta(days=2))
    old_done = assignment_factory(today - timedelta(days=1), 'Completed')
    current_done = assignment_factory(today, 'Completed')
    current_cancelled = assignment_factory(today, 'Cancelled')
    future = assignment_factory(today + timedelta(days=1))
    response = get_list(supervisor, trip_view='workbench', limit=100)
    assert response.status_code == 200, response.data
    ids = {row['unique_id'] for row in response.data['results']}
    assert ids == {a.unique_id for a in [old_running, old_scheduled, current_done, current_cancelled]}
    assert old_done.unique_id not in ids and future.unique_id not in ids
    assert response.data['service_date'] == today.isoformat()
    assert 'as_of' in response.data


def test_history_includes_cancelled_and_completed_without_logs(assignment_factory, supervisor):
    today = timezone.localdate()
    completed = assignment_factory(today, 'Completed')
    cancelled = assignment_factory(today, 'Cancelled')
    assignment_factory(today)
    assignment_factory(today - timedelta(days=8), 'Completed')
    response = get_list(supervisor, trip_view='history')
    assert response.status_code == 200, response.data
    assert {r['unique_id'] for r in response.data['results']} == {completed.unique_id, cancelled.unique_id}
    assert all(row['trip_log_summary'] is None for row in response.data['results'])
    assert all('collection_points' in row and 'trip_events' in row for row in response.data['results'])


def test_history_filters_and_pages_apply_before_serialization(assignment_factory, supervisor):
    today = timezone.localdate()
    rows = [assignment_factory(today - timedelta(days=i), 'Completed') for i in range(4)]
    assignment_factory(today, 'Cancelled')
    response = get_list(supervisor, trip_view='history', status='Completed', limit=2,
                        from_date=(today - timedelta(days=3)).isoformat(), to_date=today.isoformat())
    assert response.status_code == 200, response.data
    assert response.data['count'] == 4
    assert [r['unique_id'] for r in response.data['results']] == [a.unique_id for a in rows[:2]]
    assert response.data['next']
    second = get_list(supervisor, trip_view='history', status='Completed', limit=2, offset=2)
    assert [r['unique_id'] for r in second.data['results']] == [a.unique_id for a in rows[2:]]


def test_other_supervisor_cannot_see_assignment(assignment_factory, supervisor, driver):
    assignment_factory(timezone.localdate(), 'Completed')
    for mode in ('workbench', 'history'):
        response = get_list(driver, trip_view=mode)
        assert response.status_code == 200, response.data
        assert response.data['count'] == 0


@pytest.mark.parametrize('params', [
    {'from_date': 'not-a-date'},
    {'from_date': '2026-09-10', 'to_date': '2026-09-09'},
    {'trip_view': 'unknown'},
])
def test_invalid_filters_return_400(supervisor, params):
    response = get_list(supervisor, **{'trip_view': 'history', **params})
    assert response.status_code == 400


def test_search_matches_trip_code(assignment_factory, supervisor, bin_plan):
    trip = assignment_factory(timezone.localdate(), 'Completed')
    response = get_list(supervisor, trip_view='history', search=bin_plan.display_code)
    assert response.status_code == 200, response.data
    assert [r['unique_id'] for r in response.data['results']] == [trip.unique_id]


def test_mixed_collected_and_missed_stops_are_an_exception(assignment_factory, supervisor, collection_point, bin_obj):
    trip = assignment_factory(timezone.localdate(), 'Completed')
    second_bin = copy(bin_obj)
    second_bin.pk = None
    second_bin.unique_id = 'TEST-BIN-SECOND'
    second_bin.save()
    for sequence, state in enumerate(['Collected', 'Missed'], start=1):
        DailyTripCollectionPoint.objects.create(trip_assignment_id=trip,
            collection_point_id=collection_point, bin_id=bin_obj if sequence == 1 else second_bin, sequence=sequence,
            status=state, company_id=trip.company_id, project_id=trip.project_id,
            is_collected=state == 'Collected')
    response = get_list(supervisor, trip_view='history', exceptions_only='true')
    assert response.status_code == 200, response.data
    assert [r['unique_id'] for r in response.data['results']] == [trip.unique_id]


def test_cancel_rejects_a_trip_that_started_after_screen_loaded(assignment_factory, supervisor):
    trip = assignment_factory(timezone.localdate(), 'In Progress')
    request = APIRequestFactory().patch('/trips/status/', {
        'status': 'Cancelled', 'expected_status': 'Scheduled', 'reason': 'Not required',
    }, format='json')
    force_authenticate(request, user=supervisor)
    response = DailyTripAssignmentViewSet.as_view({'patch': 'update_status'})(request, unique_id=trip.unique_id)
    assert response.status_code == 409, response.data
    trip.refresh_from_db()
    assert trip.status == 'In Progress'
