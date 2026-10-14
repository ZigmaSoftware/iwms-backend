import pytest
from types import SimpleNamespace

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintSubcategory,
)
from app.viewsets.core_modules.complaint_management.citizen_ticket_viewset import (
    CitizenComplaintTicketViewSet,
)


@pytest.mark.django_db
def test_citizen_meta_excludes_staff_vehicle_issues(auth_client):
    pickup = ComplaintCategory.objects.create(
        category_code="MISSED_PICKUP", category_name="Missed Pickup"
    )
    vehicle = ComplaintCategory.objects.create(
        category_code="VEHICLE_ISSUE", category_name="Vehicle Issue"
    )
    ComplaintSubcategory.objects.create(
        category_id=pickup.unique_id,
        subcategory_code="WET_NOT_COLLECTED",
        subcategory_name="Wet waste not collected",
    )
    ComplaintSubcategory.objects.create(
        category_id=vehicle.unique_id,
        subcategory_code="VEHICLE_BREAKDOWN",
        subcategory_name="Vehicle broken down on route",
    )

    response = auth_client.get("/api/v1/citizen/complaint-tickets/meta/")

    assert response.status_code == 200
    assert [row["category_code"] for row in response.data["categories"]] == [
        "MISSED_PICKUP"
    ]
    assert [row["subcategory_name"] for row in response.data["subcategories"]] == [
        "Wet waste not collected"
    ]


@pytest.mark.django_db
def test_citizen_cannot_submit_vehicle_category_or_foreign_subcategory(
    household_customer,
):
    pickup = ComplaintCategory.objects.create(
        category_code="MISSED_PICKUP", category_name="Missed Pickup"
    )
    vehicle = ComplaintCategory.objects.create(
        category_code="VEHICLE_ISSUE", category_name="Vehicle Issue"
    )
    vehicle_sub = ComplaintSubcategory.objects.create(
        category_id=vehicle.unique_id,
        subcategory_code="VEHICLE_BREAKDOWN",
        subcategory_name="Vehicle broken down on route",
    )
    view = CitizenComplaintTicketViewSet()
    vehicle_response = view.create(SimpleNamespace(
        user=household_customer,
        data={"category": vehicle.unique_id, "description": "Broken vehicle"},
    ))
    mismatched_response = view.create(SimpleNamespace(
        user=household_customer,
        data={
            "category": pickup.unique_id,
            "subcategory": vehicle_sub.unique_id,
            "description": "Missed pickup",
        },
    ))

    assert vehicle_response.status_code == 400
    assert mismatched_response.status_code == 400
