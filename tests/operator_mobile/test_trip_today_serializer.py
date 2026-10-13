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
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.waste_masters.bins import Bins
from app.serializers.operator_mobile.trip_today_serializer import MyTripTodaySerializer
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    validate_customer_against_assignment,
)
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType


class _Request:
    resolved_permissions = {
        "schedule-operations": {
            "daily-trip-collection-points": ["view"],
            "daily-trip-household-collections": ["view"],
        }
    }


def _customer(company, project):
    return CustomerCreation.objects.create(
        customer_name="Household Customer",
        contact_no="9876500001",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="1111-2222-3333",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )


@pytest.mark.django_db
def test_trip_today_serializer_resolves_string_backed_vehicle_id(company, project):
    vehicle = VehicleCreation.objects.create(
        vehicle_no="UP16KT1912",
        capacity="3000.00",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    assignment = DailyTripAssignment.objects.create(
        trip_date=timezone.localdate(),
        status=DailyTripAssignment.STATUS_SCHEDULED,
        scheduled_time="07:00",
        vehicle_id=vehicle.unique_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )

    data = MyTripTodaySerializer(
        assignment,
        context={"request": _Request()},
    ).data

    assert data["vehicle"]["unique_id"] == vehicle.unique_id
    assert data["vehicle"]["vehicle_no"] == "UP16KT1912"


@pytest.mark.django_db
def test_trip_today_serializer_resolves_string_backed_bin_stop_ids(
    company,
    project,
    state,
    district,
    city,
):
    panchayat = Panchayat.objects.create(
        panchayat_name="Driver Panchayat",
        company_id=company.unique_id,
        project_id=project.unique_id,
        state_id=state.unique_id,
        district_id=district.unique_id,
        city_id=city.unique_id,
    )
    collection_point = Collection_point.objects.create(
        cp_name="Driver CP",
        company_id=company.unique_id,
        project_id=project.unique_id,
        state_id=state.unique_id,
        district_id=district.unique_id,
        city_id=city.unique_id,
        panchayat_id=panchayat.unique_id,
        latitude="13.0827",
        longitude="80.2707",
    )
    waste_type = WasteType.objects.create(waste_type_name="Wet Waste")
    bin_obj = Bins.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        collection_point_id=collection_point.unique_id,
        wastetype_id=waste_type.unique_id,
        bin_capacity=100,
        bin_type="small",
        bin_name="Driver Bin",
        bin_image="",
        bin_qr="",
    )
    assignment = DailyTripAssignment.objects.create(
        trip_date=timezone.localdate(),
        status=DailyTripAssignment.STATUS_SCHEDULED,
        scheduled_time="07:00",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    DailyTripCollectionPoint.objects.create(
        trip_assignment_id=assignment.unique_id,
        collection_point_id=collection_point.unique_id,
        bin_id=bin_obj.unique_id,
        sequence=1,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )

    data = MyTripTodaySerializer(
        assignment,
        context={"request": _Request()},
    ).data

    stop = data["collection_points"][0]
    assert stop["collection_point"]["unique_id"] == collection_point.unique_id
    assert stop["bin"]["unique_id"] == bin_obj.unique_id
    assert stop["bin"]["bin_name"] == "Driver Bin"


@pytest.mark.django_db
def test_validate_customer_against_assignment_uses_string_backed_ids(
    company,
    project,
):
    customer = _customer(company, project)
    assignment = DailyTripAssignment.objects.create(
        trip_date=timezone.localdate(),
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        scheduled_time="07:00",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    stop = DailyTripHouseholdCollection.objects.create(
        trip_assignment_id=assignment.unique_id,
        customer_id=customer.unique_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )

    assert validate_customer_against_assignment(
        customer,
        assignment,
    ).unique_id == stop.unique_id


@pytest.mark.django_db
def test_validate_customer_reports_locked_trip_without_joining_charfields(
    company,
    project,
):
    customer = _customer(company, project)
    active_assignment = DailyTripAssignment.objects.create(
        trip_date=timezone.localdate(),
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        scheduled_time="07:00",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    other_assignment = DailyTripAssignment.objects.create(
        trip_date=timezone.localdate(),
        status=DailyTripAssignment.STATUS_SCHEDULED,
        scheduled_time="09:00",
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    DailyTripHouseholdCollection.objects.create(
        trip_assignment_id=other_assignment.unique_id,
        customer_id=customer.unique_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )

    with pytest.raises(OperatorFlowError) as exc:
        validate_customer_against_assignment(customer, active_assignment)

    assert exc.value.code == "TRIP_LOCKED"
