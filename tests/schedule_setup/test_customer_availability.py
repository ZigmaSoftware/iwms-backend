from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    ComplaintTicket,
)
from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection as DTHC,
)
from app.models.core_modules.daily_operations.wastecollection import WasteCollection
from app.services import customer_availability as svc
from app.services.stale_trip_closer import close_stale_trips
from app.viewsets.core_modules.complaint_management.citizen_pickup_viewset import (
    CitizenPickupViewSet,
    _payload,
)


@pytest.fixture
def masters(company, project):
    priority = ComplaintPriority.objects.create(priority_code="P2", priority_name="P2")
    ComplaintStatus.objects.create(status_code="SUBMITTED", status_name="Submitted")
    return ComplaintCategory.objects.create(
        category_code="MISSED_PICKUP",
        category_name="Missed Pickup",
        default_priority_id=priority.unique_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )


def _stop(customer, company, project, *, status=DTHC.STATUS_COLLECT_LATER,
          trip_status="In Progress", days_ago=0):
    trip = DailyTripAssignment.objects.create(
        trip_date=timezone.localdate() - timedelta(days=days_ago),
        status=trip_status,
        scheduled_time="07:00",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    return DTHC.objects.create(
        trip_assignment_id=trip.unique_id,
        customer_id=customer.unique_id,
        status=status,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )


@pytest.fixture
def crew(monkeypatch):
    sent = []
    staff = SimpleNamespace(staff_unique_id="STF-1")
    monkeypatch.setattr(svc, "_crew_of", lambda assignment: [staff])
    monkeypatch.setattr(
        "app.services.staff_notification_service.notify_staff",
        lambda *a, **k: sent.append((a, k)),
    )
    return sent


@pytest.mark.django_db
def test_im_home_flags_stop_and_alerts_crew_once(
    household_customer, company, project, crew, django_capture_on_commit_callbacks
):
    stop = _stop(household_customer, company, project)
    with django_capture_on_commit_callbacks(execute=True):
        _, created = svc.mark_customer_available(household_customer, note="Gate open")
    stop.refresh_from_db()
    assert created is True
    assert stop.customer_available_at is not None
    assert stop.customer_available_note == "Gate open"
    assert len(crew) == 1
    assert crew[0][1]["data"]["event"] == "customer_available"

    with django_capture_on_commit_callbacks(execute=True):
        _, created = svc.mark_customer_available(household_customer)
    assert created is False
    assert len(crew) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,trip_status",
    [(DTHC.STATUS_PENDING, "In Progress"), (DTHC.STATUS_COLLECTED, "In Progress"),
     (DTHC.STATUS_COLLECT_LATER, "Completed")],
)
def test_im_home_rejected_unless_collect_later_on_running_trip(
    household_customer, company, project, crew, status, trip_status
):
    _stop(household_customer, company, project, status=status, trip_status=trip_status)
    with pytest.raises(svc.AvailabilityError):
        svc.mark_customer_available(household_customer)


@pytest.mark.django_db
def test_im_home_ignores_other_days(household_customer, company, project, crew):
    _stop(household_customer, company, project, days_ago=1)
    with pytest.raises(svc.AvailabilityError):
        svc.mark_customer_available(household_customer)


@pytest.mark.django_db
def test_driver_marking_flagged_stop_not_available_raises_one_ticket(
    household_customer, company, project, crew, masters
):
    stop = _stop(household_customer, company, project)
    svc.mark_customer_available(household_customer)
    stop.refresh_from_db()
    stop.mark_status(DTHC.STATUS_MISSED, reason="Gate locked")
    stop.mark_status(DTHC.STATUS_MISSED, reason="Gate locked")

    tickets = ComplaintTicket.objects.filter(customer_id=household_customer.unique_id)
    assert tickets.count() == 1
    ticket = tickets.first()
    assert ticket.category_id == masters.unique_id
    assert ticket.source.source_code == "SYSTEM"
    assert "Gate locked" in ticket.description


@pytest.mark.django_db
def test_unflagged_not_available_raises_no_ticket(
    household_customer, company, project, masters
):
    stop = _stop(household_customer, company, project)
    stop.mark_status(DTHC.STATUS_MISSED, reason="Nobody home")
    assert not ComplaintTicket.objects.exists()


@pytest.mark.django_db
def test_end_of_day_closer_raises_ticket_for_flagged_stop(
    household_customer, company, project, crew, masters
):
    stop = _stop(household_customer, company, project)
    svc.mark_customer_available(household_customer)
    DailyTripAssignment.objects.filter(unique_id=stop.trip_assignment_id).update(
        trip_date=timezone.localdate() - timedelta(days=1)
    )

    close_stale_trips()

    stop.refresh_from_db()
    assert stop.status == DTHC.STATUS_MISSED
    assert svc.missed_pickup_ticket(stop) is not None


@pytest.mark.django_db
def test_citizen_endpoint_reports_status_and_ticket(
    household_customer, company, project, crew, masters
):
    stop = _stop(household_customer, company, project)
    view = CitizenPickupViewSet()
    request = SimpleNamespace(user=household_customer, data={"note": "Home"})

    body = view.im_home(request).data
    assert body["notified"] is True
    assert body["stop"]["customer_available_at"] is not None

    stop.refresh_from_db()
    stop.mark_status(DTHC.STATUS_MISSED)
    body = view.list(SimpleNamespace(user=household_customer)).data
    assert body["stop"]["status"] == DTHC.STATUS_MISSED
    assert body["stop"]["missed_pickup_ticket_no"]


@pytest.mark.django_db
def test_citizen_endpoint_explains_rejection(household_customer, company, project):
    _stop(household_customer, company, project, status=DTHC.STATUS_PENDING)
    response = CitizenPickupViewSet().im_home(
        SimpleNamespace(user=household_customer, data={})
    )
    assert response.status_code == 400
    assert "Collect Later" in response.data["detail"]


@pytest.mark.django_db
def test_collected_pickup_payload_includes_proof_and_waste_breakdown(
    household_customer, company, project
):
    stop = _stop(
        household_customer,
        company,
        project,
        status=DTHC.STATUS_PENDING,
    )
    collection = WasteCollection.objects.create(
        customer_id=household_customer.unique_id,
        trip_assignment_id=stop.trip_assignment_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
        collection_date=timezone.localdate(),
        status=WasteCollection.STATUS_COLLECTED,
        wet_waste=1.5,
        mixed_waste=2,
        image="waste_collection_images/proof.jpg",
    )
    stop.refresh_from_db()

    request = SimpleNamespace(
        build_absolute_uri=lambda path: f"https://iwms.example{path}"
    )
    body = _payload(stop, request)["stop"]

    assert stop.waste_collection_id == collection.unique_id
    assert body["collection_image_url"] == (
        "https://iwms.example/media/waste_collection_images/proof.jpg"
    )
    assert body["waste_breakdown"] == [
        {"waste_type": "Wet Waste", "weight_kg": 1.5},
        {"waste_type": "Mixed Waste", "weight_kg": 2.0},
    ]


@pytest.mark.django_db
def test_exception_pickup_payload_includes_status_evidence(
    household_customer, company, project
):
    stop = _stop(
        household_customer,
        company,
        project,
        status=DTHC.STATUS_COLLECT_LATER,
    )
    stop.status_evidence_image = "household_status_evidence/proof.jpg"
    stop.save(update_fields=["status_evidence_image", "updated_at"])

    request = SimpleNamespace(
        build_absolute_uri=lambda path: f"https://iwms.example{path}"
    )
    body = _payload(stop, request)["stop"]

    assert body["status_evidence_image_url"] == (
        "https://iwms.example/media/household_status_evidence/proof.jpg"
    )
