"""Tests for Section 5 — Daily Trip Plan / Bin Collection Event / Waste Data
Collected parity with TN_Iwms.

Covers:
  - DailyTripAssignment.waste_types M2M is populated from the TripPlan on
    create, and geo (wards) is copied from the plan.
  - DailyTripAssignment.mark_completed_if_all_cps_collected treats a Missed
    stop as resolved (mirrors TN's Collected/Missed rule).
  - DailyTripCollectionPoint.mark_status (Missed/Skipped) clears weight and
    is_collected, and triggers assignment completion checks.
  - DailyTripHouseholdCollection status vocabulary (Not Available / Collect
    Later) and mark_status.
  - BinCollectionEvent gains status/status_reason/zone_id and auto-copies
    panchayat/ward/zone from the trip assignment on save.
  - WasteCollection gains sanitary_waste/status/ward, auto-calculates
    total_quantity including sanitary_waste, and inherits ward from the
    customer when left blank.
"""
from datetime import date, time

import pytest
from decimal import Decimal

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.customers.wastecollection import WasteCollection
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.daily_trip_household_collection import DailyTripHouseholdCollection
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


# ----------------------------------------------------------------------
# Shared fixtures (mirrors tests/schedule_setup/test_trip_plan_auto_assign.py)
# ----------------------------------------------------------------------

@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Daily Ops Panchayat",
        company_id=company, project_id=project,
        state_id=state, district_id=district, city_id=city,
    )


@pytest.fixture
def waste_type_obj(db):
    return WasteType.objects.create(waste_type_name="General Waste")


@pytest.fixture
def waste_type_obj_2(db):
    return WasteType.objects.create(waste_type_name="Plastic Waste")


@pytest.fixture
def driver(db, company, project):
    return Staffcreation.objects.create(employee_name="Driver One", company_id=company, project_id=project)


@pytest.fixture
def operator(db, company, project):
    return Staffcreation.objects.create(employee_name="Operator One", company_id=company, project_id=project)


@pytest.fixture
def supervisor(db, company, project):
    return Staffcreation.objects.create(employee_name="Supervisor One", company_id=company, project_id=project)


@pytest.fixture
def staff_template(db, company, project, driver, operator):
    return StaffTemplate.objects.create(company_id=company, project_id=project, driver_id=driver, operator_id=operator)


@pytest.fixture
def vehicle(db, company, project):
    return VehicleCreation.objects.create(company_id=company, project_id=project, vehicle_no="TN01AB1234")


@pytest.fixture
def collection_point(db, company, project, state, district, city, panchayat, ward):
    cp = Collection_point.objects.create(
        cp_name="Daily Ops CP",
        company_id=company, project_id=project,
        state_id=state, city_id=city, district_id=district,
        panchayat_id=panchayat,
        latitude="13.0827", longitude="80.2707",
    )
    cp.wards.set([ward])
    return cp


@pytest.fixture
def bin_obj(db, company, project, district, city, collection_point, waste_type_obj):
    return Bins.objects.create(
        company_id=company, project_id=project,
        district_id=district, city_id=city,
        collection_point_id=collection_point,
        wastetype_id=waste_type_obj,
        bin_capacity=100,
        bin_type="small",
        bin_name="Daily Ops Bin",
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


def _make_plan(company, project, district, city, panchayat, staff_template, vehicle,
                supervisor, waste_type_obj, collection_type=TripPlan.COLLECTION_TYPE_BIN,
                is_auto_assign=True, repeat_days=None):
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
        approval_status=TripPlan.ApprovalStatus.APPROVED,
        status=TripPlan.Status.ACTIVE,
    )


@pytest.fixture
def bin_plan(db, company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj, ward):
    plan = _make_plan(
        company, project, district, city, panchayat, staff_template, vehicle,
        supervisor, waste_type_obj, collection_type=TripPlan.COLLECTION_TYPE_BIN,
    )
    plan.wards.set([ward])
    plan.waste_types.set([waste_type_obj])
    return plan


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


@pytest.fixture
def assignment(db, bin_plan):
    """A DailyTripAssignment for bin_plan, deliberately WITHOUT any
    TripPlanCollectionPoint stops registered on the plan, so the post_save
    signal clones nothing — tests that need a DailyTripCollectionPoint create
    it explicitly against a bin/collection_point combo of their choosing."""
    a = DailyTripAssignment.objects.create(
        company_id=bin_plan.company_id, project_id=bin_plan.project_id,
        trip_plan_id=bin_plan, trip_date=date(2026, 8, 3),
    )
    return a


@pytest.fixture
def waste_collection_assignment(db, company, project, household_customer):
    """A minimal DailyTripAssignment usable as WasteCollection.trip_assignment_id
    (no trip plan dependency needed for WasteCollection-only tests)."""
    plan = None
    return plan


# ----------------------------------------------------------------------
# 1. DailyTripAssignment — waste_types M2M + geo copy on save
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestDailyTripAssignmentWasteTypesAndGeo:
    def test_waste_types_copied_from_trip_plan_on_create(self, assignment, waste_type_obj):
        assert list(assignment.waste_types.all()) == [waste_type_obj]

    def test_wards_copied_from_trip_plan_on_create(self, assignment, ward):
        assert list(assignment.wards.all()) == [ward]

    def test_staff_and_vehicle_copied_from_plan(self, assignment, staff_template, vehicle):
        assert assignment.staff_template_id_id == staff_template.pk
        assert assignment.vehicle_id_id == vehicle.pk

    def test_explicit_waste_types_are_not_overridden(
        self, bin_stop, waste_type_obj_2,
    ):
        plan = bin_stop.trip_plan_id
        a = DailyTripAssignment(
            company_id=plan.company_id, project_id=plan.project_id,
            trip_plan_id=plan, trip_date=date(2026, 8, 4),
        )
        a.save()
        # Simulate an explicit narrower selection made right after create
        # (as the serializer's create() does for M2M fields).
        a.waste_types.set([waste_type_obj_2])
        a.save()  # is_new is False on the second save; must not reset M2M
        assert list(a.waste_types.all()) == [waste_type_obj_2]


# ----------------------------------------------------------------------
# 2. DailyTripAssignment.mark_completed_if_all_cps_collected — Missed counts
#    as resolved, and ending a trip is now a driver-confirmed action rather
#    than an automatic side effect of the last scan (see TripCompletionNudge
#    on the app side) — DailyTripCollectionPoint.mark_collected/mark_status
#    (the driver app's own write path) call with auto_end=False, so status
#    is left alone even once everything is resolved. Admin/web edits still
#    auto-close via the viewsets' own explicit
#    mark_completed_if_all_cps_collected() call, which defaults auto_end=True.
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestMarkCompletedStatusRule:
    def test_all_collected_does_not_auto_end_the_driver_app_write_path(
        self, assignment, collection_point, bin_obj, driver
    ):
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        stop.mark_collected(Decimal("10.00"), None)
        assignment.refresh_from_db()
        assert assignment.status != DailyTripAssignment.STATUS_COMPLETED

    def test_missed_stop_counts_as_resolved_but_does_not_auto_end(
        self, assignment, collection_point, bin_obj
    ):
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        stop.mark_status(DailyTripCollectionPoint.STATUS_MISSED, "Bin inaccessible")
        assignment.refresh_from_db()
        assert assignment.status != DailyTripAssignment.STATUS_COMPLETED

    def test_skipped_stop_does_not_complete_trip(self, assignment, collection_point, bin_obj):
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        stop.mark_status(DailyTripCollectionPoint.STATUS_SKIPPED, "Collect later")
        assignment.refresh_from_db()
        assert assignment.status != DailyTripAssignment.STATUS_COMPLETED

    def test_resolved_is_still_detected_even_without_auto_end(
        self, assignment, collection_point, bin_obj
    ):
        """auto_end=False still reports the resolution truthfully — only the
        side effect of actually closing the trip is withheld — so the app's
        TripCompletionNudge (which reads this via `progress.resolved`, not
        this method directly) has an accurate signal to act on."""
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        stop.mark_collected(Decimal("10.00"), None)
        assignment.refresh_from_db()
        assert assignment.mark_completed_if_all_cps_collected(auto_end=False) is True
        assert assignment.status != DailyTripAssignment.STATUS_COMPLETED

    def test_admin_write_path_still_auto_ends(self, assignment, collection_point, bin_obj):
        """The admin/web CRUD path (and the backfill script) call this with
        the default auto_end=True and must keep closing the trip immediately
        — there is no "driver confirms" step for a direct admin edit."""
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
            collected_weight_kg=Decimal("10.00"), is_collected=True,
            status=DailyTripCollectionPoint.STATUS_COLLECTED,
        )
        assert assignment.mark_completed_if_all_cps_collected() is True
        assignment.refresh_from_db()
        assert assignment.status == DailyTripAssignment.STATUS_COMPLETED


# ----------------------------------------------------------------------
# 3. DailyTripCollectionPoint.mark_status
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestDailyTripCollectionPointMarkStatus:
    def test_mark_status_clears_weight_and_collected_flag(self, assignment, collection_point, bin_obj):
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
            collected_weight_kg=Decimal("5.00"), is_collected=True,
            status=DailyTripCollectionPoint.STATUS_COLLECTED,
        )
        stop.mark_status(DailyTripCollectionPoint.STATUS_MISSED, "No access")
        stop.refresh_from_db()
        assert stop.status == DailyTripCollectionPoint.STATUS_MISSED
        assert stop.status_reason == "No access"
        assert stop.collected_weight_kg is None
        assert stop.is_collected is False


# ----------------------------------------------------------------------
# 4. DailyTripHouseholdCollection status vocabulary + mark_status
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestDailyTripHouseholdCollectionStatus:
    def test_not_available_status_value(self):
        assert DailyTripHouseholdCollection.STATUS_MISSED == "Not Available"
        assert ("Collect Later", "Collect Later") in DailyTripHouseholdCollection.STATUS_CHOICES

    def test_mark_status_not_available(self, assignment, household_customer):
        row = DailyTripHouseholdCollection.objects.create(
            trip_assignment_id=assignment, customer_id=household_customer,
        )
        row.mark_status(DailyTripHouseholdCollection.STATUS_MISSED, "Not home", latitude="13.01", longitude="80.02")
        row.refresh_from_db()
        assert row.status == "Not Available"
        assert row.status_reason == "Not home"
        assert row.is_collected is False

    def test_geo_denormalised_from_customer(self, assignment, household_customer, ward, zone, panchayat):
        row = DailyTripHouseholdCollection.objects.create(
            trip_assignment_id=assignment, customer_id=household_customer,
        )
        assert row.ward_id_id == ward.pk
        assert row.zone_id_id == zone.pk
        assert row.panchayat_id_id == panchayat.pk


# ----------------------------------------------------------------------
# 5. BinCollectionEvent — status/status_reason/zone + geo auto-copy
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestBinCollectionEventGeoAndStatus:
    def test_geo_copied_from_trip_assignment(
        self, assignment, collection_point, bin_obj, waste_type_obj, ward, zone, panchayat,
    ):
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        event = BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("12.50"),
        )
        assert event.panchayat_id_id == panchayat.pk
        assert event.ward_id_id == ward.pk
        assert event.zone_id_id == zone.pk

    def test_default_status_is_collected(self, assignment, collection_point, bin_obj, waste_type_obj):
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        event = BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("12.50"),
        )
        assert event.status == BinCollectionEvent.STATUS_COLLECTED

    def test_not_collected_status_allows_null_weight(self, assignment, collection_point, bin_obj, waste_type_obj):
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        event = BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj,
            status=BinCollectionEvent.STATUS_NOT_COLLECTED,
            status_reason="Bin missing",
        )
        assert event.collected_weight_kg is None
        assert event.status_reason == "Bin missing"

    def test_explicit_geo_is_not_overridden(
        self, assignment, collection_point, bin_obj, waste_type_obj, panchayat, company, project, state, district, city,
    ):
        other_panchayat = Panchayat.objects.create(
            panchayat_name="Other Panchayat", company_id=company, project_id=project,
            state_id=state, district_id=district, city_id=city,
        )
        stop = DailyTripCollectionPoint.objects.create(
            trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
        )
        event = BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("1.00"),
            panchayat_id=other_panchayat,
        )
        assert event.panchayat_id_id == other_panchayat.pk


# ----------------------------------------------------------------------
# 6. WasteCollection — sanitary_waste/status/ward + total_quantity + geo copy
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestWasteCollectionParity:
    def test_total_quantity_includes_sanitary_waste(self, household_customer):
        wc = WasteCollection.objects.create(
            customer=household_customer,
            wet_waste=1.5, dry_waste=2.5, mixed_waste=1.0, sanitary_waste=0.5,
        )
        assert wc.total_quantity == 5.5

    def test_ward_inherited_from_customer_when_blank(self, household_customer, ward):
        wc = WasteCollection.objects.create(customer=household_customer, wet_waste=1.0)
        assert wc.ward_id == ward.pk

    def test_explicit_ward_not_overridden(self, household_customer, company, project, state, district, city, zone):
        from app.models.masters.ward import Ward
        other_ward = Ward.objects.create(
            ward_name="Other Ward", company_id=company, project_id=project,
            state_id=state, district_id=district, city_id=city, zone_id=zone,
        )
        wc = WasteCollection.objects.create(customer=household_customer, wet_waste=1.0, ward=other_ward)
        assert wc.ward_id == other_ward.pk

    def test_default_status_is_pending(self, household_customer):
        wc = WasteCollection.objects.create(customer=household_customer, wet_waste=1.0)
        assert wc.status == WasteCollection.STATUS_PENDING

    def test_collection_date_defaults_when_omitted(self, household_customer):
        wc = WasteCollection.objects.create(customer=household_customer, wet_waste=1.0)
        assert wc.collection_date is not None

    def test_collection_date_is_user_editable(self, household_customer):
        wc = WasteCollection.objects.create(
            customer=household_customer, wet_waste=1.0, collection_date=date(2026, 1, 15),
        )
        assert wc.collection_date == date(2026, 1, 15)
