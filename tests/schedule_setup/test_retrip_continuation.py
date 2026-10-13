from datetime import time

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
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.waste_masters.bins import Bins
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.services import retrip_service

pytestmark = pytest.mark.django_db


def _assignment(plan):
    return DailyTripAssignment.objects.create(
        trip_plan_id=plan.unique_id,
        staff_template_id=plan.staff_template_id,
        vehicle_id=plan.vehicle_id,
        trip_date=timezone.localdate(),
        scheduled_time=plan.scheduled_time,
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
        company_id=plan.company_id,
        project_id=plan.project_id,
        panchayat_id=plan.panchayat_id,
        waste_type_ids=plan.waste_type_ids,
    )


def _household_plan(
    company,
    project,
    district,
    city,
    panchayat,
    staff_template,
    vehicle,
    supervisor,
    waste_type_obj,
):
    return TripPlan.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        district_id=district.unique_id,
        city_id=city.unique_id,
        panchayat_id=panchayat.unique_id,
        staff_template_id=staff_template.unique_id,
        vehicle_id=vehicle.unique_id,
        supervisor_id=supervisor.staff_unique_id,
        waste_type_id=waste_type_obj.unique_id,
        waste_type_ids=[waste_type_obj.unique_id],
        trip_trigger_weight_kg=800,
        max_vehicle_capacity_kg=3000,
        scheduled_time=time(6, 0),
        collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
        is_auto_assign=True,
        repeat_days=[],
        approval_status=TripPlan.ApprovalStatus.APPROVED,
        status=TripPlan.Status.ACTIVE,
    )


def _customer(
    company,
    project,
    country,
    state,
    district,
    city,
    zone,
    ward,
    panchayat,
    prop,
    sub_prop,
    suffix,
):
    return CustomerCreation.objects.create(
        customer_name=f"Household Customer {suffix}",
        contact_no=f"98765010{suffix:02d}",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no=f"1111-2222-{suffix:04d}",
        company_id=company.unique_id,
        project_id=project.unique_id,
        country_id=country.unique_id,
        state_id=state.unique_id,
        district_id=district.unique_id,
        city_id=city.unique_id,
        zone_id=zone.unique_id,
        ward_id=ward.unique_id,
        panchayat_id=panchayat.unique_id,
        property_id=prop.unique_id,
        sub_property_id=sub_prop.unique_id,
        is_bulkwaste_generator=False,
    )


def test_retrip_approval_copies_household_stops_from_source_when_plan_expands_empty(
    company,
    project,
    country,
    state,
    district,
    city,
    zone,
    ward,
    panchayat,
    prop,
    sub_prop,
    staff_template,
    vehicle,
    supervisor,
    waste_type_obj,
):
    plan = _household_plan(
        company,
        project,
        district,
        city,
        panchayat,
        staff_template,
        vehicle,
        supervisor,
        waste_type_obj,
    )
    TripPlanCollectionPoint.objects.create(
        trip_plan_id=plan.unique_id,
        collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
        sequence=1,
        is_active=True,
    )
    source = _assignment(plan)

    customers = [
        _customer(
            company,
            project,
            country,
            state,
            district,
            city,
            zone,
            ward,
            panchayat,
            prop,
            sub_prop,
            suffix,
        )
        for suffix in range(1, 4)
    ]
    for sequence, customer in enumerate(customers, start=1):
        DailyTripHouseholdCollection.objects.create(
            trip_assignment_id=source.unique_id,
            customer_id=customer.unique_id,
            collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD,
            sequence=sequence,
            status=DailyTripHouseholdCollection.STATUS_PENDING,
            company_id=company.unique_id,
            project_id=project.unique_id,
            zone_id=zone.unique_id,
            ward_id=ward.unique_id,
            panchayat_id=panchayat.unique_id,
        )

    # Simulate the live failure mode: approval-time plan expansion can no
    # longer find customers, but the source trip still has pending rows.
    CustomerCreation.objects.update(is_active=False)

    request = retrip_service.request_retrip(
        source,
        requested_by=staff_template.driver,
        reason="Truck full",
    )
    continuation = retrip_service.approve_retrip(
        request,
        reviewed_by=supervisor,
        collection_point_ids=None,
        remarks="Approved",
    )

    carried = DailyTripHouseholdCollection.objects.filter(
        trip_assignment_id=continuation.unique_id,
        is_deleted=False,
    ).order_by("sequence")
    assert carried.count() == 3
    assert [row.customer_id for row in carried] == [c.unique_id for c in customers]
    assert all(row.status == DailyTripHouseholdCollection.STATUS_PENDING for row in carried)
    assert not DailyTripCollectionPoint.objects.filter(
        trip_assignment_id=continuation.unique_id,
        is_deleted=False,
    ).exists()

    request.refresh_from_db()
    source.refresh_from_db()
    assert request.new_assignment_id == continuation.unique_id
    assert source.status == DailyTripAssignment.STATUS_COMPLETED


def test_retrip_approval_carries_only_selected_bin_stops(
    company,
    project,
    district,
    city,
    panchayat,
    staff_template,
    vehicle,
    supervisor,
    waste_type_obj,
):
    plan = TripPlan.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        district_id=district.unique_id,
        city_id=city.unique_id,
        panchayat_id=panchayat.unique_id,
        staff_template_id=staff_template.unique_id,
        vehicle_id=vehicle.unique_id,
        supervisor_id=supervisor.staff_unique_id,
        waste_type_id=waste_type_obj.unique_id,
        waste_type_ids=[waste_type_obj.unique_id],
        trip_trigger_weight_kg=800,
        max_vehicle_capacity_kg=3000,
        scheduled_time=time(6, 0),
        collection_type=TripPlan.COLLECTION_TYPE_BIN,
        is_auto_assign=True,
        repeat_days=[],
        approval_status=TripPlan.ApprovalStatus.APPROVED,
        status=TripPlan.Status.ACTIVE,
    )
    source = _assignment(plan)
    wet = WasteType.objects.create(waste_type_name="Wet")

    stops = []
    for sequence in range(1, 4):
        collection_point = Collection_point.objects.create(
            cp_name=f"CP {sequence}",
            company_id=company.unique_id,
            project_id=project.unique_id,
            district_id=district.unique_id,
            city_id=city.unique_id,
            panchayat_id=panchayat.unique_id,
            latitude="13.0827",
            longitude="80.2707",
        )
        bin_obj = Bins.objects.create(
            company_id=company.unique_id,
            project_id=project.unique_id,
            district_id=district.unique_id,
            city_id=city.unique_id,
            collection_point_id=collection_point.unique_id,
            wastetype_id=wet.unique_id,
            bin_capacity=100,
            bin_type="small",
            bin_name=f"Bin {sequence}",
            bin_image="",
            bin_qr="",
        )
        stops.append(
            DailyTripCollectionPoint.objects.create(
                trip_assignment_id=source.unique_id,
                collection_point_id=collection_point.unique_id,
                bin_id=bin_obj.unique_id,
                sequence=sequence,
                status=DailyTripCollectionPoint.STATUS_PENDING,
                company_id=company.unique_id,
                project_id=project.unique_id,
                panchayat_id=panchayat.unique_id,
            )
        )

    request = retrip_service.request_retrip(
        source,
        requested_by=staff_template.driver,
        reason="Need another trip",
    )
    continuation = retrip_service.approve_retrip(
        request,
        reviewed_by=supervisor,
        collection_point_ids=[stops[0].unique_id, stops[2].unique_id],
        remarks="Approved",
    )

    carried = DailyTripCollectionPoint.objects.filter(
        trip_assignment_id=continuation.unique_id,
        is_deleted=False,
    ).order_by("sequence")
    assert [row.collection_point_id for row in carried] == [
        stops[0].collection_point_id,
        stops[2].collection_point_id,
    ]
    assert not DailyTripHouseholdCollection.objects.filter(
        trip_assignment_id=continuation.unique_id,
        is_deleted=False,
    ).exists()
