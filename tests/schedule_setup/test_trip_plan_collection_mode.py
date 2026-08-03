"""Tests for the Trip Plan "Collection Mode" auto-assign flow.

TripPlan.collection_type (bin_collection / household_collection /
bulk_waste_collection) drives whether a plan's stop list is manually
entered (bin) or auto-expanded server-side to every matching customer in
the plan's ward/panchayat scope (household/bulk), via a single catch-all
TripPlanCollectionPoint row with no customer_id.

Covers:
  - TripPlanSerializer actually persists TripPlan.collection_type (it was
    previously accepted by the model but never read/written by the
    serializer, so it silently stayed at its default).
  - A household/bulk stop with no customer_id (the catch-all/auto-assign
    row) is accepted by validate() and persisted with plan-derived geo.
  - A stop's collection_type must match the plan's collection_type.
  - Only one catch-all stop is allowed per plan.
  - The catch-all stop expands to every matching customer in scope via
    run_for_date (end-to-end: serializer -> signal -> DailyTripHouseholdCollection).
"""
import pytest

from app.management.commands.generate_daily_trips import run_for_date
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_household_collection import DailyTripHouseholdCollection
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.serializers.core_modules.schedule_setup.trip_plan_serializer import TripPlanSerializer


@pytest.fixture
def ward_household_customer(db, company, project, continent, country, state, district, city,
                             panchayat, panchayat_ward, prop, sub_prop):
    return CustomerCreation.objects.create(
        customer_name="Ward Household Customer",
        contact_no="9876500011",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="1111-9999-3333",
        company_id=company, project_id=project,
        country=country, state=state, district=district,
        city=city, ward=panchayat_ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
        is_bulkwaste_generator=False,
    )


@pytest.fixture
def ward_bulk_customer(db, company, project, continent, country, state, district, city,
                        panchayat, panchayat_ward, prop, sub_prop):
    return CustomerCreation.objects.create(
        customer_name="Ward Bulk Customer",
        contact_no="9876500022",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="4444-9999-6666",
        company_id=company, project_id=project,
        country=country, state=state, district=district,
        city=city, ward=panchayat_ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
        is_bulkwaste_generator=True,
    )


def _base_payload(company, project, district, city, panchayat, panchayat_ward, staff_template,
                   vehicle, supervisor, waste_type_obj, collection_type, collection_points):
    return {
        "company_id_input": company.unique_id,
        "project_id_input": project.unique_id,
        "district_id": district.unique_id,
        "city_id": city.unique_id,
        "panchayat_id": panchayat.unique_id,
        "ward_ids": [panchayat_ward.unique_id],
        "staff_template_id": staff_template.unique_id,
        "vehicle_id": vehicle.unique_id,
        "supervisor_id": supervisor.staff_unique_id,
        "waste_type_ids": [waste_type_obj.unique_id],
        "trip_trigger_weight_kg": 800,
        "max_vehicle_capacity_kg": 3000,
        "scheduled_time": "06:00",
        "collection_type": collection_type,
        "is_auto_assign": True,
        "repeat_days": [0, 1, 2, 3, 4, 5, 6],
        "approval_status": TripPlan.ApprovalStatus.APPROVED,
        "status": TripPlan.Status.ACTIVE,
        "collection_points": collection_points,
    }


@pytest.mark.django_db
class TestCollectionTypePersisted:
    def test_household_mode_is_saved_on_the_plan(
        self, company, project, district, city, panchayat, panchayat_ward, staff_template,
        vehicle, supervisor, waste_type_obj,
    ):
        payload = _base_payload(
            company, project, district, city, panchayat, panchayat_ward, staff_template,
            vehicle, supervisor, waste_type_obj,
            collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            collection_points=[{"collection_type": "household_collection", "sequence": 1}],
        )
        serializer = TripPlanSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        plan = serializer.save(company_id=company, project_id=project)
        plan.refresh_from_db()
        assert plan.collection_type == TripPlan.COLLECTION_TYPE_HOUSEHOLD

    def test_bin_mode_is_saved_on_the_plan(
        self, company, project, district, city, panchayat, panchayat_ward, staff_template,
        vehicle, supervisor, waste_type_obj, collection_point, bin_obj,
    ):
        payload = _base_payload(
            company, project, district, city, panchayat, panchayat_ward, staff_template,
            vehicle, supervisor, waste_type_obj,
            collection_type=TripPlan.COLLECTION_TYPE_BIN,
            collection_points=[{
                "collection_type": "bin_collection",
                "collection_point_id": collection_point.unique_id,
                "bin_id": bin_obj.unique_id,
                "sequence": 1,
            }],
        )
        serializer = TripPlanSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        plan = serializer.save(company_id=company, project_id=project)
        plan.refresh_from_db()
        assert plan.collection_type == TripPlan.COLLECTION_TYPE_BIN


@pytest.mark.django_db
class TestCatchAllStopValidation:
    def test_household_stop_without_customer_id_is_accepted(
        self, company, project, district, city, panchayat, panchayat_ward, staff_template,
        vehicle, supervisor, waste_type_obj,
    ):
        payload = _base_payload(
            company, project, district, city, panchayat, panchayat_ward, staff_template,
            vehicle, supervisor, waste_type_obj,
            collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            collection_points=[{"collection_type": "household_collection", "sequence": 1}],
        )
        serializer = TripPlanSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        plan = serializer.save(company_id=company, project_id=project)

        stops = TripPlanCollectionPoint.objects.filter(trip_plan_id=plan, is_deleted=False)
        assert stops.count() == 1
        stop = stops.first()
        assert stop.customer_id_id is None
        assert stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD
        # Geo copied from the plan since there's no single customer to derive it from.
        assert stop.panchayat_id_id == panchayat.unique_id

    def test_only_one_catch_all_stop_allowed(
        self, company, project, district, city, panchayat, panchayat_ward, staff_template,
        vehicle, supervisor, waste_type_obj,
    ):
        payload = _base_payload(
            company, project, district, city, panchayat, panchayat_ward, staff_template,
            vehicle, supervisor, waste_type_obj,
            collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            collection_points=[
                {"collection_type": "household_collection", "sequence": 1},
                {"collection_type": "household_collection", "sequence": 2},
            ],
        )
        serializer = TripPlanSerializer(data=payload)
        assert not serializer.is_valid()
        assert "collection_points" in serializer.errors

    def test_stop_type_must_match_plan_collection_type(
        self, company, project, district, city, panchayat, panchayat_ward, staff_template,
        vehicle, supervisor, waste_type_obj, collection_point, bin_obj,
    ):
        payload = _base_payload(
            company, project, district, city, panchayat, panchayat_ward, staff_template,
            vehicle, supervisor, waste_type_obj,
            collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            collection_points=[{
                "collection_type": "bin_collection",
                "collection_point_id": collection_point.unique_id,
                "bin_id": bin_obj.unique_id,
                "sequence": 1,
            }],
        )
        serializer = TripPlanSerializer(data=payload)
        assert not serializer.is_valid()
        assert "collection_points" in serializer.errors


@pytest.mark.django_db
class TestCatchAllStopExpandsToCustomers:
    def test_household_catch_all_expands_to_matching_customers(
        self, company, project, district, city, panchayat, panchayat_ward, staff_template,
        vehicle, supervisor, waste_type_obj, ward_household_customer, ward_bulk_customer,
    ):
        payload = _base_payload(
            company, project, district, city, panchayat, panchayat_ward, staff_template,
            vehicle, supervisor, waste_type_obj,
            collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            collection_points=[{"collection_type": "household_collection", "sequence": 1}],
        )
        serializer = TripPlanSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        plan = serializer.save(company_id=company, project_id=project)

        target_date = __import__("datetime").date(2026, 8, 3)  # Monday
        run_for_date(target_date=target_date)

        assignment = DailyTripAssignment.objects.get(trip_plan_id=plan, trip_date=target_date)
        rows = DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment)
        # Only the non-bulk customer in scope should be picked up for a
        # household-mode plan; the bulk generator is excluded.
        assert rows.count() == 1
        assert rows.first().customer_id_id == ward_household_customer.unique_id
        assert rows.first().collection_type == DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD

    def test_bulk_catch_all_expands_to_bulk_customers_only(
        self, company, project, district, city, panchayat, panchayat_ward, staff_template,
        vehicle, supervisor, waste_type_obj, ward_household_customer, ward_bulk_customer,
    ):
        payload = _base_payload(
            company, project, district, city, panchayat, panchayat_ward, staff_template,
            vehicle, supervisor, waste_type_obj,
            collection_type=TripPlan.COLLECTION_TYPE_BULK,
            collection_points=[{"collection_type": "bulk_waste_collection", "sequence": 1}],
        )
        serializer = TripPlanSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        plan = serializer.save(company_id=company, project_id=project)

        target_date = __import__("datetime").date(2026, 8, 3)  # Monday
        run_for_date(target_date=target_date)

        assignment = DailyTripAssignment.objects.get(trip_plan_id=plan, trip_date=target_date)
        rows = DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment)
        assert rows.count() == 1
        assert rows.first().customer_id_id == ward_bulk_customer.unique_id
        assert rows.first().collection_type == DailyTripHouseholdCollection.COLLECTION_TYPE_BULK
