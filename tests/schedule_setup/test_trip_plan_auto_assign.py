"""Tests for Section 4 — TripPlan auto-assign / daily trip generation parity.

Covers:
  - is_auto_assign filter actually excludes non-flagged plans (bug fix)
  - idempotency of stop cloning (bin + household + bulk), calling twice
    never duplicates rows
  - force vs non-force weekday/approval semantics in run_for_date
  - the generate_daily action endpoint on DailyTripAssignmentViewSet
"""
import pytest
from rest_framework.test import APIClient

from app.management.commands.generate_daily_trips import run_for_date
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.daily_trip_household_collection import DailyTripHouseholdCollection
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint

from tests.schedule_setup.conftest import _make_plan


# ----------------------------------------------------------------------
# Item 3: is_auto_assign filter
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestIsAutoAssignFilter:
    def test_non_auto_assign_plan_is_excluded(
        self, company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj,
    ):
        plan = _make_plan(
            company, project, district, city, panchayat, staff_template, vehicle,
            supervisor, waste_type_obj, is_auto_assign=False,
            repeat_days=[0, 1, 2, 3, 4, 5, 6],
        )
        target_date = __import__("datetime").date(2026, 8, 3)  # Monday
        summary = run_for_date(target_date=target_date)
        assert not DailyTripAssignment.objects.filter(trip_plan_id=plan).exists()
        assert summary["created"] == 0

    def test_auto_assign_plan_is_included(
        self, company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj, bin_stop,
    ):
        plan = bin_stop.trip_plan_id
        target_date = __import__("datetime").date(2026, 8, 3)  # Monday
        plan.repeat_days = [0, 1, 2, 3, 4, 5, 6]
        plan.save(update_fields=["repeat_days"])
        summary = run_for_date(target_date=target_date)
        assert DailyTripAssignment.objects.filter(trip_plan_id=plan, trip_date=target_date).exists()
        assert summary["created"] == 1


# ----------------------------------------------------------------------
# Idempotency of stop cloning
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestIdempotentStopCloning:
    def test_running_twice_does_not_duplicate_bin_stops(self, bin_stop):
        plan = bin_stop.trip_plan_id
        plan.repeat_days = [0, 1, 2, 3, 4, 5, 6]
        plan.save(update_fields=["repeat_days"])
        target_date = __import__("datetime").date(2026, 8, 3)

        run_for_date(target_date=target_date)
        assignment = DailyTripAssignment.objects.get(trip_plan_id=plan, trip_date=target_date)
        assert DailyTripCollectionPoint.objects.filter(trip_assignment_id=assignment).count() == 1

        # Re-run for the same date — must not duplicate.
        run_for_date(target_date=target_date)
        assert DailyTripCollectionPoint.objects.filter(trip_assignment_id=assignment).count() == 1

    def test_running_twice_does_not_duplicate_household_stops(
        self, company, project, district, city, panchayat, staff_template, vehicle, supervisor,
        waste_type_obj, household_customer,
    ):
        plan = _make_plan(
            company, project, district, city, panchayat, staff_template, vehicle,
            supervisor, waste_type_obj, collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            repeat_days=[0, 1, 2, 3, 4, 5, 6],
        )
        TripPlanCollectionPoint.objects.create(
            trip_plan_id=plan,
            collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
            customer_id=household_customer,
            sequence=1,
            is_active=True,
        )
        target_date = __import__("datetime").date(2026, 8, 3)

        run_for_date(target_date=target_date)
        assignment = DailyTripAssignment.objects.get(trip_plan_id=plan, trip_date=target_date)
        assert DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment).count() == 1

        run_for_date(target_date=target_date)
        assert DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment).count() == 1

    def test_bulk_stop_creates_bulk_collection_type(
        self, company, project, district, city, panchayat, staff_template, vehicle, supervisor,
        waste_type_obj, bulk_customer,
    ):
        plan = _make_plan(
            company, project, district, city, panchayat, staff_template, vehicle,
            supervisor, waste_type_obj, collection_type=TripPlan.COLLECTION_TYPE_BULK,
            repeat_days=[0, 1, 2, 3, 4, 5, 6],
        )
        TripPlanCollectionPoint.objects.create(
            trip_plan_id=plan,
            collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
            customer_id=bulk_customer,
            sequence=1,
            is_active=True,
        )
        target_date = __import__("datetime").date(2026, 8, 3)
        run_for_date(target_date=target_date)
        assignment = DailyTripAssignment.objects.get(trip_plan_id=plan, trip_date=target_date)
        rows = DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment)
        assert rows.count() == 1
        assert rows.first().collection_type == DailyTripHouseholdCollection.COLLECTION_TYPE_BULK


# ----------------------------------------------------------------------
# force vs non-force semantics
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestForceSemantics:
    def test_non_force_skips_wrong_weekday(self, bin_stop):
        plan = bin_stop.trip_plan_id
        plan.repeat_days = [1]  # Tuesday only
        plan.save(update_fields=["repeat_days"])
        monday = __import__("datetime").date(2026, 8, 3)  # Monday
        summary = run_for_date(target_date=monday, force=False)
        assert summary["created"] == 0
        assert not DailyTripAssignment.objects.filter(trip_plan_id=plan, trip_date=monday).exists()

    def test_force_ignores_weekday(self, bin_stop):
        plan = bin_stop.trip_plan_id
        plan.repeat_days = [1]  # Tuesday only
        plan.save(update_fields=["repeat_days"])
        monday = __import__("datetime").date(2026, 8, 3)  # Monday
        summary = run_for_date(target_date=monday, force=True)
        assert summary["created"] == 1
        assert DailyTripAssignment.objects.filter(trip_plan_id=plan, trip_date=monday).exists()

    def test_non_force_excludes_unapproved_plan(
        self, company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj,
    ):
        plan = _make_plan(
            company, project, district, city, panchayat, staff_template, vehicle,
            supervisor, waste_type_obj, approval_status=TripPlan.ApprovalStatus.PENDING,
            repeat_days=[0, 1, 2, 3, 4, 5, 6],
        )
        monday = __import__("datetime").date(2026, 8, 3)
        summary = run_for_date(target_date=monday, force=False)
        assert summary["created"] == 0
        assert not DailyTripAssignment.objects.filter(trip_plan_id=plan).exists()

    def test_force_includes_unapproved_plan(
        self, company, project, district, city, panchayat, staff_template, vehicle, supervisor, waste_type_obj,
    ):
        plan = _make_plan(
            company, project, district, city, panchayat, staff_template, vehicle,
            supervisor, waste_type_obj, approval_status=TripPlan.ApprovalStatus.PENDING,
            repeat_days=[0, 1, 2, 3, 4, 5, 6],
        )
        monday = __import__("datetime").date(2026, 8, 3)
        summary = run_for_date(target_date=monday, force=True)
        assert summary["created"] == 1
        assert DailyTripAssignment.objects.filter(trip_plan_id=plan, trip_date=monday).exists()


# ----------------------------------------------------------------------
# generate_daily action endpoint
# ----------------------------------------------------------------------

@pytest.mark.django_db
class TestGenerateDailyAction:
    def test_endpoint_generates_assignment(self, auth_client, bin_stop):
        plan = bin_stop.trip_plan_id
        plan.repeat_days = [0, 1, 2, 3, 4, 5, 6]
        plan.save(update_fields=["repeat_days"])

        response = auth_client.post(
            "/api/v1/schedule-operations/daily-trip-assignments/generate-daily/",
            data={"date": "2026-08-03"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["created"] == 1
        assert DailyTripAssignment.objects.filter(
            trip_plan_id=plan, trip_date="2026-08-03"
        ).exists()

    def test_endpoint_is_idempotent(self, auth_client, bin_stop):
        plan = bin_stop.trip_plan_id
        plan.repeat_days = [0, 1, 2, 3, 4, 5, 6]
        plan.save(update_fields=["repeat_days"])

        auth_client.post(
            "/api/v1/schedule-operations/daily-trip-assignments/generate-daily/",
            data={"date": "2026-08-03"},
            format="json",
        )
        response = auth_client.post(
            "/api/v1/schedule-operations/daily-trip-assignments/generate-daily/",
            data={"date": "2026-08-03"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["created"] == 0
        assert DailyTripAssignment.objects.filter(
            trip_plan_id=plan, trip_date="2026-08-03"
        ).count() == 1
