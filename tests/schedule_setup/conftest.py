"""Shared fixtures for schedule_setup trip-plan / daily-trip tests."""
from datetime import time

import pytest

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Auto-Assign Panchayat",
        company_id=company, project_id=project,
        state_id=state, district_id=district, city_id=city,
    )


@pytest.fixture
def panchayat_ward(db, state, district, city, panchayat):
    from app.models.masters.ward import Ward
    return Ward.objects.create(
        ward_name="Auto-Assign Ward",
        state_id=state, district_id=district, city_id=city,
        panchayat_id=panchayat,
    )


@pytest.fixture
def waste_type_obj(db):
    return WasteType.objects.create(waste_type_name="General Waste")


@pytest.fixture
def driver(db, company, project):
    return Staffcreation.objects.create(
        employee_name="Driver One", company_id=company, project_id=project,
    )


@pytest.fixture
def operator(db, company, project):
    return Staffcreation.objects.create(
        employee_name="Operator One", company_id=company, project_id=project,
    )


@pytest.fixture
def supervisor(db, company, project):
    return Staffcreation.objects.create(
        employee_name="Supervisor One", company_id=company, project_id=project,
    )


@pytest.fixture
def staff_template(db, company, project, driver, operator):
    return StaffTemplate.objects.create(
        company_id=company, project_id=project,
        driver_id=driver, operator_id=operator,
    )


@pytest.fixture
def vehicle(db, company, project):
    return VehicleCreation.objects.create(
        company_id=company, project_id=project,
        vehicle_no="TN01AB1234",
    )


@pytest.fixture
def collection_point(db, company, project, state, district, city, panchayat):
    return Collection_point.objects.create(
        cp_name="Auto-Assign CP",
        company_id=company, project_id=project,
        state_id=state, city_id=city, district_id=district,
        panchayat_id=panchayat,
        latitude="13.0827", longitude="80.2707",
    )


@pytest.fixture
def bin_obj(db, company, project, district, city, collection_point, waste_type_obj):
    return Bins.objects.create(
        company_id=company, project_id=project,
        district_id=district, city_id=city,
        collection_point_id=collection_point,
        wastetype_id=waste_type_obj,
        bin_capacity=100,
        bin_type="small",
        bin_name="Auto-Assign Bin",
        bin_image="",
        bin_qr="",
    )


@pytest.fixture
def prop(db):
    return Property.objects.create(property_name="Residential")


@pytest.fixture
def sub_prop(db, prop):
    return SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)


@pytest.fixture
def household_customer(db, company, project, continent, country, state, district, city, zone, ward, panchayat, prop, sub_prop):
    return CustomerCreation.objects.create(
        customer_name="Household Customer",
        contact_no="9876500001",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="1111-2222-3333",
        company_id=company, project_id=project,
        country=country, state=state, district=district,
        city=city, zone=zone, ward=ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
        is_bulkwaste_generator=False,
    )


@pytest.fixture
def bulk_customer(db, company, project, continent, country, state, district, city, zone, ward, panchayat, prop, sub_prop):
    return CustomerCreation.objects.create(
        customer_name="Bulk Customer",
        contact_no="9876500002",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="4444-5555-6666",
        company_id=company, project_id=project,
        country=country, state=state, district=district,
        city=city, zone=zone, ward=ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
        is_bulkwaste_generator=True,
    )


def _make_plan(company, project, district, city, panchayat, staff_template, vehicle,
                supervisor, waste_type_obj, collection_type=TripPlan.COLLECTION_TYPE_BIN,
                is_auto_assign=True, repeat_days=None, approval_status=TripPlan.ApprovalStatus.APPROVED,
                status=TripPlan.Status.ACTIVE):
    return TripPlan.objects.create(
        company_id=company, project_id=project,
        district_id=district, city_id=city,
        panchayat_id=panchayat,
        staff_template_id=staff_template,
        vehicle_id=vehicle,
        supervisor_id=supervisor,
        waste_type_id=waste_type_obj,
        waste_type_ids=[waste_type_obj.unique_id],
        trip_trigger_weight_kg=800,
        max_vehicle_capacity_kg=3000,
        scheduled_time=time(6, 0),
        collection_type=collection_type,
        is_auto_assign=is_auto_assign,
        repeat_days=repeat_days if repeat_days is not None else [],
        approval_status=approval_status,
        status=status,
    )


@pytest.fixture
def bin_plan(db, company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj):
    return _make_plan(
        company, project, district, city, panchayat, staff_template, vehicle,
        supervisor, waste_type_obj, collection_type=TripPlan.COLLECTION_TYPE_BIN,
    )


@pytest.fixture
def bin_stop(db, bin_plan, collection_point, bin_obj):
    return TripPlanCollectionPoint.objects.create(
        trip_plan_id=bin_plan,
        collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
        collection_point_id=collection_point,
        bin_id=bin_obj,
        sequence=1,
        is_active=True,
    )
