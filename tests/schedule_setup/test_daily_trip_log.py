"""Tests for Section 6 — Daily Trip Log parity with TN_Iwms.

Covers:
  - autofill_from_assignment(): copies company/project, geo (panchayat/zone
    via wards fallback), staff template (+ alt), driver/operator (+ extra
    operators via effective template), vehicle, waste type, trip_date, and
    actual start/end times from the linked DailyTripAssignment.
  - sync_from_bin_collection_events(): sums BinCollectionEvent.collected_weight_kg,
    only overriding when records exist; None-weight (Not Collected) events do
    not break the aggregate (Sum ignores NULLs).
  - sync_from_household_collections(): sums WasteCollection.total_quantity,
    only overriding when records exist.
  - Status flow Unverified -> Verified; read-only once Verified; weight > 0
    required before verifying; blocked creation for cancelled trips.
  - Once actual_end_time is set, the linked DailyTripAssignment is marked
    Completed and actual_end_time is set on it too.
"""
from datetime import date, time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from app.models.customers.customercreation import CustomerCreation
from app.models.customers.wastecollection import WasteCollection
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.assets.bins import Bins
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


# ----------------------------------------------------------------------
# Shared fixtures (mirrors tests/schedule_setup/test_daily_ops_parity.py)
# ----------------------------------------------------------------------

@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Trip Log Panchayat",
        company_id=company, project_id=project,
        state_id=state, district_id=district, city_id=city,
    )


@pytest.fixture
def waste_type_obj(db):
    return WasteType.objects.create(waste_type_name="General Waste")


@pytest.fixture
def driver(db, company, project):
    return Staffcreation.objects.create(employee_name="Driver One", company_id=company, project_id=project)


@pytest.fixture
def operator(db, company, project):
    return Staffcreation.objects.create(employee_name="Operator One", company_id=company, project_id=project)


@pytest.fixture
def alt_driver(db, company, project):
    return Staffcreation.objects.create(employee_name="Alt Driver", company_id=company, project_id=project)


@pytest.fixture
def alt_operator(db, company, project):
    return Staffcreation.objects.create(employee_name="Alt Operator", company_id=company, project_id=project)


@pytest.fixture
def supervisor(db, company, project):
    return Staffcreation.objects.create(employee_name="Supervisor One", company_id=company, project_id=project)


@pytest.fixture
def extra_op(db, company, project):
    return Staffcreation.objects.create(employee_name="Extra Operator", company_id=company, project_id=project)


@pytest.fixture
def staff_template(db, company, project, driver, operator):
    return StaffTemplate.objects.create(company_id=company, project_id=project, driver_id=driver, operator_id=operator)


@pytest.fixture
def alt_staff_template(db, company, project, staff_template, alt_driver, alt_operator):
    return AlternativeStaffTemplate.objects.create(
        staff_template=staff_template,
        company_id=company, project_id=project, driver_id=alt_driver, operator_id=alt_operator,
    )


@pytest.fixture
def vehicle(db, company, project):
    return VehicleCreation.objects.create(company_id=company, project_id=project, vehicle_no="TN01LOG1234")


@pytest.fixture
def collection_point(db, company, project, state, district, city, panchayat, ward):
    cp = Collection_point.objects.create(
        cp_name="Trip Log CP",
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
        bin_name="Trip Log Bin",
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
        customer_name="Trip Log Household",
        contact_no="9876500002",
        pincode="600002",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="2222-3333-4444",
        company_id=company, project_id=project,
        country=country, state=state, district=district,
        city=city, zone=zone, ward=ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
        is_bulkwaste_generator=False,
    )


def _make_plan(company, project, district, city, panchayat, staff_template, vehicle,
                supervisor, waste_type_obj, is_auto_assign=False):
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
        collection_type=TripPlan.COLLECTION_TYPE_BIN,
        is_auto_assign=is_auto_assign,
        repeat_days=[],
        approval_status=TripPlan.ApprovalStatus.APPROVED,
        status=TripPlan.Status.ACTIVE,
    )


@pytest.fixture
def bin_plan(db, company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj, ward):
    plan = _make_plan(company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj)
    plan.wards.set([ward])
    plan.waste_types.set([waste_type_obj])
    return plan


@pytest.fixture
def assignment(db, bin_plan):
    return DailyTripAssignment.objects.create(
        company_id=bin_plan.company_id, project_id=bin_plan.project_id,
        trip_plan_id=bin_plan, trip_date=date(2026, 8, 3),
        actual_start_time=time(7, 0),
    )


@pytest.fixture
def assignment_with_alt(db, assignment, alt_staff_template):
    assignment.alt_staff_template_id = alt_staff_template
    assignment.save(update_fields=["alt_staff_template_id"])
    return assignment


@pytest.fixture
def stop(db, assignment, collection_point, bin_obj):
    return DailyTripCollectionPoint.objects.create(
        trip_assignment_id=assignment, collection_point_id=collection_point, bin_id=bin_obj,
    )


def _make_log(assignment, **kwargs):
    return DailyTripLog.objects.create(trip_assignment_id=assignment, **kwargs)


# ----------------------------------------------------------------------
# 1. autofill_from_assignment
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestAutofillFromAssignment:
    def test_company_and_project_copied(self, assignment):
        log = _make_log(assignment)
        assert log.company_id_id == assignment.company_id_id
        assert log.project_id_id == assignment.project_id_id

    def test_geo_copied_via_ward_fallback(self, assignment, panchayat):
        # assignment has no panchayat_id/zone_id of its own but has one ward
        # whose panchayat is set — autofill should derive panchayat from it.
        log = _make_log(assignment)
        assert log.panchayat_id_id == panchayat.pk

    def test_staff_template_and_alt_copied(self, assignment_with_alt, alt_staff_template, staff_template):
        log = _make_log(assignment_with_alt)
        assert log.staff_template_id_id == staff_template.pk
        assert log.alt_staff_template_id_id == alt_staff_template.pk

    def test_driver_and_operator_from_effective_template(self, assignment, driver, operator):
        # No alt template -> effective template is the base staff_template.
        log = _make_log(assignment)
        assert log.driver_id_id == driver.pk
        assert log.operator_id_id == operator.pk

    def test_driver_and_operator_prefer_alt_template(self, assignment_with_alt, alt_driver, alt_operator):
        log = _make_log(assignment_with_alt)
        assert log.driver_id_id == alt_driver.pk
        assert log.operator_id_id == alt_operator.pk

    def test_extra_operators_settable(self, assignment, extra_op):
        log = _make_log(assignment)
        log.extra_operator_ids.set([extra_op])
        assert list(log.extra_operator_ids.all()) == [extra_op]

    def test_vehicle_copied(self, assignment, vehicle):
        log = _make_log(assignment)
        assert log.vehicle_id_id == vehicle.pk

    def test_waste_type_copied(self, assignment, waste_type_obj):
        log = _make_log(assignment)
        assert log.waste_type_id_id == waste_type_obj.pk

    def test_trip_date_copied(self, assignment):
        log = _make_log(assignment)
        assert log.trip_date == assignment.trip_date

    def test_actual_start_time_copied_when_unset(self, assignment):
        log = _make_log(assignment)
        assert log.actual_start_time == time(7, 0)

    def test_actual_start_time_explicit_not_overridden(self, assignment):
        log = _make_log(assignment, actual_start_time=time(8, 30))
        assert log.actual_start_time == time(8, 30)

    def test_collection_point_defaulted_from_first_stop(self, assignment, stop, collection_point):
        log = _make_log(assignment)
        assert log.collection_point_id_id == collection_point.pk

    def test_unique_id_generated(self, assignment):
        log = _make_log(assignment)
        today = date.today()
        assert log.unique_id.startswith(f"DTL-{today.year}-{today.month:02d}-")


# ----------------------------------------------------------------------
# 2. Weight sync
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestWeightSync:
    def test_bin_events_summed(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("10.00"),
        )
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("5.50"),
        )
        log = _make_log(assignment)
        assert log.collected_weight_kg == Decimal("15.50")

    def test_bin_events_none_weight_ignored_by_sum(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        # A "Not Collected" event has collected_weight_kg=None; Sum must
        # ignore NULLs rather than blow up or coerce to a falsy total.
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj,
            status=BinCollectionEvent.STATUS_NOT_COLLECTED,
            status_reason="Bin missing",
        )
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("7.25"),
        )
        log = _make_log(assignment)
        assert log.collected_weight_kg == Decimal("7.25")

    def test_bin_weight_not_overridden_when_no_events(self, assignment):
        log = _make_log(assignment, collected_weight_kg=Decimal("42.00"))
        log.refresh_from_db()
        assert log.collected_weight_kg == Decimal("42.00")

    def test_household_collections_summed(self, assignment, household_customer):
        # Creating a WasteCollection against an assignment auto-creates the
        # DailyTripLog via sync_household_collection_on_waste_save (a real
        # IWMS enhancement beyond TN's manual-create-only flow) — so no
        # separate _make_log() call here, just fetch what the signal made.
        WasteCollection.objects.create(
            trip_assignment_id=assignment, customer=household_customer,
            wet_waste=2.0, dry_waste=1.0,
        )
        WasteCollection.objects.create(
            trip_assignment_id=assignment, customer=household_customer,
            sanitary_waste=0.5,
        )
        log = DailyTripLog.objects.get(trip_assignment_id=assignment)
        assert log.household_collected_weight_kg == Decimal("3.5")

    def test_household_weight_not_overridden_when_no_records(self, assignment):
        log = _make_log(assignment, household_collected_weight_kg=Decimal("9.00"))
        log.refresh_from_db()
        assert log.household_collected_weight_kg == Decimal("9.00")


# ----------------------------------------------------------------------
# 3. Status flow
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestStatusFlow:
    def test_default_status_is_unverified(self, assignment):
        log = _make_log(assignment)
        assert log.log_status == DailyTripLog.LOG_STATUS_UNVERIFIED

    def test_creation_blocked_for_cancelled_trip(self, assignment):
        assignment.status = DailyTripAssignment.STATUS_CANCELLED
        assignment.save(update_fields=["status"])
        with pytest.raises(ValidationError):
            _make_log(assignment)

    def test_verify_requires_weight_greater_than_zero(self, assignment):
        log = _make_log(assignment)  # Unverified, no weight yet
        log.log_status = DailyTripLog.LOG_STATUS_VERIFIED
        with pytest.raises(ValidationError):
            log.save()

    def test_verify_succeeds_with_positive_weight(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("3.00"),
        )
        log = _make_log(assignment)  # auto-synced to 3.00 on create
        log.log_status = DailyTripLog.LOG_STATUS_VERIFIED
        log.save()
        log.refresh_from_db()
        assert log.log_status == DailyTripLog.LOG_STATUS_VERIFIED

    def test_verified_log_is_read_only(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("3.00"),
        )
        log = _make_log(assignment)
        log.log_status = DailyTripLog.LOG_STATUS_VERIFIED
        log.save()

        log.remarks = "trying to edit after verify"
        with pytest.raises(ValidationError):
            log.save()


# ----------------------------------------------------------------------
# 4. actual_end_time marks assignment Completed
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestAssignmentCompletionOnEndTime:
    def test_end_time_marks_assignment_completed(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("3.00"),
        )
        log = _make_log(assignment, actual_end_time=time(9, 45))
        assignment.refresh_from_db()
        assert assignment.status == DailyTripAssignment.STATUS_COMPLETED

    def test_end_time_sets_actual_end_time_when_unset(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        assert assignment.actual_end_time is None
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("3.00"),
        )
        log = _make_log(assignment, actual_end_time=time(9, 45))
        assignment.refresh_from_db()
        assert assignment.actual_end_time == time(9, 45)

    def test_end_time_does_not_override_existing_actual_end_time(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        assignment.actual_end_time = time(10, 0)
        assignment.save(update_fields=["actual_end_time"])
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("3.00"),
        )
        log = _make_log(assignment, actual_end_time=time(11, 30))
        assignment.refresh_from_db()
        assert assignment.actual_end_time == time(10, 0)

    def test_verify_also_marks_assignment_completed(self, assignment, stop, collection_point, bin_obj, waste_type_obj):
        BinCollectionEvent.objects.create(
            company_id=assignment.company_id, project_id=assignment.project_id,
            trip_assignment_id=assignment, trip_collection_point_id=stop,
            collection_point_id=collection_point, bin_id=bin_obj,
            waste_type_id=waste_type_obj, collected_weight_kg=Decimal("3.00"),
        )
        log = _make_log(assignment, actual_end_time=time(9, 45))
        log.log_status = DailyTripLog.LOG_STATUS_VERIFIED
        log.save()
        assignment.refresh_from_db()
        assert assignment.status == DailyTripAssignment.STATUS_COMPLETED

    def test_no_end_time_does_not_touch_assignment_status(self, assignment):
        log = _make_log(assignment)
        assignment.refresh_from_db()
        assert assignment.status == DailyTripAssignment.STATUS_SCHEDULED
