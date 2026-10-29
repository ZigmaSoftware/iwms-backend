"""Web form: raise a Pending Re-Trip request on a driver's behalf."""
import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.viewsets.core_modules.daily_operations.trip_retrip_viewset import TripRetripRequestViewSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def trip(bin_plan, collection_point, bin_obj):
    def create(status="In Progress", stop_status="Pending"):
        assignment = DailyTripAssignment.objects.create(
            trip_plan_id=bin_plan.unique_id, staff_template_id=bin_plan.staff_template_id,
            company_id=bin_plan.company_id, project_id=bin_plan.project_id,
            vehicle_id=bin_plan.vehicle_id, trip_date=timezone.localdate(),
            scheduled_time=bin_plan.scheduled_time, status=status,
            approval_status="Approved", waste_type_ids=bin_plan.waste_type_ids,
        )
        DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment.unique_id, collection_point_id=collection_point.unique_id,
            bin_id=bin_obj.unique_id, sequence=1, status=stop_status,
            company_id=assignment.company_id, project_id=assignment.project_id,
            is_collected=stop_status == "Collected",
        )
        return assignment
    return create


def post_create(user, data):
    request = APIRequestFactory().post("/retrip-requests/", data, format="json")
    force_authenticate(request, user=user)
    return TripRetripRequestViewSet.as_view({"post": "create"})(request)


def get_pending_stops(user, assignment_id):
    request = APIRequestFactory().get(
        "/retrip-requests/pending-stops/", {"assignment_id": assignment_id}
    )
    force_authenticate(request, user=user)
    return TripRetripRequestViewSet.as_view({"get": "pending_stops"})(request)


def test_create_raises_pending_request_and_trip_stays_in_progress(trip, supervisor):
    assignment = trip()
    response = post_create(supervisor, {"assignment_id": assignment.unique_id, "reason": "Vehicle full"})
    assert response.status_code == 201, response.data
    assert response.data["status"] == "Pending"
    assert response.data["pending_bin_count"] == 1
    assert response.data["requested_by_id"] == supervisor.staff_unique_id
    assignment.refresh_from_db()
    assert assignment.status == "In Progress"


def test_create_requires_reason(trip, supervisor):
    response = post_create(supervisor, {"assignment_id": trip().unique_id, "reason": "  "})
    assert response.status_code == 400, response.data
    assert not TripRetripRequest.objects.exists()


def test_create_rejects_second_pending_request(trip, supervisor):
    assignment = trip()
    assert post_create(supervisor, {"assignment_id": assignment.unique_id, "reason_code": "VEHICLE_FULL"}).status_code == 201
    response = post_create(supervisor, {"assignment_id": assignment.unique_id, "reason_code": "SHIFT_END"})
    assert response.status_code == 409, response.data
    assert TripRetripRequest.objects.count() == 1


def test_create_rejects_trip_without_pending_stops(trip, supervisor):
    response = post_create(
        supervisor, {"assignment_id": trip(stop_status="Collected").unique_id, "reason_code": "VEHICLE_FULL"}
    )
    assert response.status_code == 400, response.data


def test_create_rejects_closed_trip(trip, supervisor):
    response = post_create(supervisor, {"assignment_id": trip(status="Completed").unique_id, "reason_code": "VEHICLE_FULL"})
    assert response.status_code == 400, response.data


def test_pending_stops_preview(trip, supervisor, collection_point):
    response = get_pending_stops(supervisor, trip().unique_id)
    assert response.status_code == 200, response.data
    assert [s["collection_point_id"] for s in response.data["collection_points"]] == [
        collection_point.unique_id
    ]
    assert response.data["households"] == []


def test_create_with_reason_code_needs_no_text(trip, supervisor):
    response = post_create(
        supervisor, {"assignment_id": trip().unique_id, "reason_code": "VEHICLE_FULL"}
    )
    assert response.status_code == 201, response.data
    assert response.data["reason_code"] == "VEHICLE_FULL"
    assert response.data["reason_code_label"] == "Vehicle full"
    assert response.data["reason"] == "Vehicle full"


def test_create_with_reason_code_keeps_the_note(trip, supervisor):
    response = post_create(
        supervisor,
        {"assignment_id": trip().unique_id, "reason_code": "ROAD_BLOCKED", "reason": "Ward 5 flooded"},
    )
    assert response.status_code == 201, response.data
    assert response.data["reason"] == "Road blocked: Ward 5 flooded"


def test_create_rejects_too_short_other_reason(trip, supervisor):
    response = post_create(
        supervisor, {"assignment_id": trip().unique_id, "reason_code": "OTHER", "reason": "ok"}
    )
    assert response.status_code == 400, response.data
    assert "at least 10 characters" in response.data["reason"]
    assert not TripRetripRequest.objects.exists()


def test_create_without_code_is_treated_as_other(trip, supervisor):
    """Older clients send free text only: it must meet the "Other" bar."""
    short = post_create(supervisor, {"assignment_id": trip().unique_id, "reason": "."})
    assert short.status_code == 400, short.data

    ok = post_create(
        supervisor, {"assignment_id": trip().unique_id, "reason": "Crew called in sick"}
    )
    assert ok.status_code == 201, ok.data
    assert ok.data["reason_code"] == "OTHER"


def test_create_rejects_unknown_reason_code(trip, supervisor):
    response = post_create(
        supervisor, {"assignment_id": trip().unique_id, "reason_code": "BOGUS"}
    )
    assert response.status_code == 400, response.data


def test_reason_codes_endpoint_lists_categories(supervisor):
    request = APIRequestFactory().get("/retrip-requests/reason-codes/")
    force_authenticate(request, user=supervisor)
    response = TripRetripRequestViewSet.as_view({"get": "reason_codes"})(request)
    assert response.status_code == 200
    assert {"value": "OTHER", "label": "Other"} in response.data
