"""Breakdown scenarios for the days after: the broken vehicle's trip plans
run on a replacement vehicle with their own crew until it is repaired."""

from datetime import time, timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from app.management.commands.generate_daily_trips import run_for_date
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.vehicle_breakdown import (
    VehicleBreakdown,
    sync_vehicle_operational_status,
)
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_vehicle_substitution import (
    TripPlanVehicleSubstitution,
)
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
    VehicleBreakdownMarkRepairedSerializer,
    VehicleBreakdownVerifySerializer,
)
from app.services import vehicle_substitution
from app.utils.cascade_soft_delete import cascade_soft_delete

pytestmark = pytest.mark.django_db

def _today():
    return timezone.localdate()


def _trips(plan, day):
    return DailyTripAssignment.objects.filter(
        trip_plan_id=plan.unique_id, trip_date=day, is_deleted=False,
    )


def _status(vehicle_id):
    return VehicleCreation.objects.get(unique_id=vehicle_id).operational_status


@pytest.fixture
def source_trip(bin_plan, bin_stop):
    return DailyTripAssignment.objects.create(
        company_id=bin_plan.company_id,
        project_id=bin_plan.project_id,
        trip_plan_id=bin_plan.unique_id,
        staff_template_id=bin_plan.staff_template_id,
        vehicle_id=bin_plan.vehicle_id,
        panchayat_id=bin_plan.panchayat_id,
        waste_type_ids=bin_plan.waste_type_ids,
        trip_date=_today(),
        scheduled_time=time(9, 0),
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
    )


@pytest.fixture
def breakdown(bin_plan, source_trip):
    row = VehicleBreakdown.objects.create(
        company_id=bin_plan.company_id,
        project_id=bin_plan.project_id,
        trip_assignment_id=source_trip.unique_id,
        breakdown_vehicle_id=bin_plan.vehicle_id,
    )
    sync_vehicle_operational_status(bin_plan.vehicle_id)
    return row


@pytest.fixture
def spare(bin_plan):
    return VehicleCreation.objects.create(
        company_id=bin_plan.company_id, project_id=bin_plan.project_id, vehicle_no="TN01SPARE",
    )


def _verify(breakdown, spare, **extra):
    serializer = VehicleBreakdownVerifySerializer(
        data={"replacement_vehicle_id": spare.unique_id, **extra},
        context={
            "instance": breakdown,
            "request": SimpleNamespace(user=SimpleNamespace(staffusertype=None)),
            "account": None,
        },
    )
    assert serializer.is_valid(), serializer.errors
    return serializer.save()


def _second_plan(bin_plan, vehicle_id, *, repeat_days=None, at=time(14, 0)):
    return TripPlan.objects.create(
        company_id=bin_plan.company_id,
        project_id=bin_plan.project_id,
        district_id=bin_plan.district_id,
        city_id=bin_plan.city_id,
        panchayat_id=bin_plan.panchayat_id,
        staff_template_id=bin_plan.staff_template_id,
        vehicle_id=vehicle_id,
        supervisor_id=bin_plan.supervisor_id,
        waste_type_id=bin_plan.waste_type_id,
        waste_type_ids=bin_plan.waste_type_ids,
        trip_trigger_weight_kg=800,
        max_vehicle_capacity_kg=3000,
        scheduled_time=at,
        collection_type=bin_plan.collection_type,
        is_auto_assign=True,
        repeat_days=repeat_days or [],
        approval_status=TripPlan.ApprovalStatus.APPROVED,
        status=TripPlan.Status.ACTIVE,
    )


# ── S1 same crew carries on ───────────────────────────────────────────


def test_s1_verify_defaults_to_the_same_crew(bin_plan, breakdown, spare, staff_template):
    approved = _verify(breakdown, spare)
    assert approved.replacement_driver_id == staff_template.driver_id
    assert approved.replacement_operator_id == staff_template.operator_id


# ── S4 next days run on the replacement with the same crew ────────────


def test_s4_next_day_trip_runs_on_replacement_with_plan_crew(bin_plan, breakdown, spare):
    approved = _verify(breakdown, spare)
    assert approved.substituted_plan_ids == [bin_plan.unique_id]

    substitution = TripPlanVehicleSubstitution.objects.get(trip_plan_id=bin_plan.unique_id)
    assert substitution.from_date == _today() + timedelta(days=1)
    assert substitution.vehicle_breakdown_id == breakdown.unique_id

    tomorrow = _today() + timedelta(days=1)
    run_for_date(target_date=tomorrow, force=True)
    trip = _trips(bin_plan, tomorrow).get()
    assert trip.vehicle_id == spare.unique_id
    assert trip.staff_template_id == bin_plan.staff_template_id


def test_s4_supervisor_can_untick_the_plan(bin_plan, breakdown, spare):
    approved = _verify(breakdown, spare, substitute_plan_ids=[])
    assert approved.substituted_plan_ids == []
    assert not TripPlanVehicleSubstitution.objects.exists()


# ── S5 / "available for one trip only": warn, supervisor confirms ─────


def test_s5_busy_spare_is_not_used_unless_confirmed(bin_plan, breakdown, spare):
    _second_plan(bin_plan, spare.unique_id)  # the spare's own daily plan

    preview = vehicle_substitution.verify_preview(breakdown, spare.unique_id)
    plan_row = preview["plans"][0]
    assert plan_row["default_substitute"] is False
    assert plan_row["clashes"][0]["kind"] == "own_plan"

    assert _verify(breakdown, spare).substituted_plan_ids == []


def test_s5_supervisor_confirms_a_busy_spare(bin_plan, breakdown, spare):
    _second_plan(bin_plan, spare.unique_id)
    approved = _verify(breakdown, spare, substitute_plan_ids=[bin_plan.unique_id])
    assert approved.substituted_plan_ids == [bin_plan.unique_id]


def test_s5_no_clash_when_the_days_do_not_overlap(bin_plan, breakdown, spare):
    bin_plan.repeat_days = [0, 1]  # Mon, Tue
    bin_plan.save(update_fields=["repeat_days"])
    _second_plan(bin_plan, spare.unique_id, repeat_days=[2])  # Wed
    assert vehicle_substitution.plan_clashes(spare.unique_id, bin_plan, _today()) == []


def test_a_trip_is_unticked_when_the_spare_is_busy_that_day(bin_plan, breakdown, spare):
    later = DailyTripAssignment.objects.create(
        company_id=bin_plan.company_id, project_id=bin_plan.project_id,
        trip_plan_id=bin_plan.unique_id, vehicle_id=bin_plan.vehicle_id,
        trip_date=_today(), scheduled_time=time(11, 0),
        status=DailyTripAssignment.STATUS_SCHEDULED,
    )
    DailyTripAssignment.objects.create(
        company_id=bin_plan.company_id, project_id=bin_plan.project_id,
        trip_plan_id=bin_plan.unique_id, vehicle_id=spare.unique_id,
        trip_date=_today(), scheduled_time=time(11, 30),
        status=DailyTripAssignment.STATUS_SCHEDULED,
    )
    preview = vehicle_substitution.verify_preview(breakdown, spare.unique_id)
    row = next(t for t in preview["upcoming_trips"] if t["unique_id"] == later.unique_id)
    assert row["default_move"] is False
    assert row["replacement_busy"]


# ── S6 / S8 no usable replacement: skip and tell the supervisor once ──


def test_s6_no_replacement_skips_and_alerts_supervisor_once(bin_plan, breakdown, supervisor):
    tomorrow = _today() + timedelta(days=1)
    run_for_date(target_date=tomorrow, force=True)
    run_for_date(target_date=tomorrow, force=True)

    assert not _trips(bin_plan, tomorrow).exists()
    alerts = StaffNotification.objects.filter(
        recipient_staff_id=supervisor.staff_unique_id,
        notification_type=StaffNotification.TYPE_TRIP_NOT_SCHEDULED,
    )
    assert alerts.count() == 1


def test_s8_replacement_also_broken_skips(bin_plan, breakdown, spare):
    _verify(breakdown, spare)
    VehicleCreation.objects.filter(pk=spare.pk).update(
        operational_status=VehicleCreation.OperationalStatus.BREAKDOWN,
    )
    tomorrow = _today() + timedelta(days=1)
    summary = run_for_date(target_date=tomorrow, force=True)

    assert not _trips(bin_plan, tomorrow).exists()
    assert summary["skipped_breakdown"][0]["reason"] == vehicle_substitution.REASON_REPLACEMENT_BROKEN


# ── S7 repaired: back to the original vehicle ─────────────────────────


def test_s7_repair_ends_substitution_and_original_vehicle_returns(bin_plan, breakdown, spare):
    approved = _verify(breakdown, spare)
    repaired = VehicleBreakdownMarkRepairedSerializer(data={}, context={"instance": approved})
    repaired.is_valid(raise_exception=True)
    repaired.save()

    substitution = TripPlanVehicleSubstitution.objects.get(trip_plan_id=bin_plan.unique_id)
    assert substitution.status == TripPlanVehicleSubstitution.STATUS_ENDED
    assert substitution.end_reason == "Vehicle back in service"

    tomorrow = _today() + timedelta(days=1)
    run_for_date(target_date=tomorrow, force=True)
    assert _trips(bin_plan, tomorrow).get().vehicle_id == bin_plan.vehicle_id


# ── S9 vehicle broken and crew on leave ───────────────────────────────


def test_s9_alternative_crew_and_replacement_vehicle_both_apply(
    bin_plan, breakdown, spare, staff_template, driver, operator,
):
    _verify(breakdown, spare)
    tomorrow = _today() + timedelta(days=1)
    leave_cover = AlternativeStaffTemplate.objects.create(
        staff_template_id=staff_template.unique_id,
        driver_id=operator.staff_unique_id,
        operator_id=driver.staff_unique_id,
        from_date=tomorrow,
        to_date=tomorrow,
        approval_status="APPROVED",
        change_reason="Leave",
    )
    run_for_date(target_date=tomorrow, force=True)
    trip = _trips(bin_plan, tomorrow).get()
    assert trip.vehicle_id == spare.unique_id
    assert trip.alt_staff_template_id == leave_cover.unique_id


def test_s9_breakdown_replacement_crew_is_not_used_as_leave_cover(bin_plan, breakdown, spare):
    """Verify makes an undated alternative crew for the continuation; it must
    not leak into the following days' trips."""
    _verify(breakdown, spare)
    tomorrow = _today() + timedelta(days=1)
    run_for_date(target_date=tomorrow, force=True)
    assert _trips(bin_plan, tomorrow).get().alt_staff_template_id is None


# ── S13 one vehicle, two plans ────────────────────────────────────────


def test_s13_every_plan_of_the_broken_vehicle_is_covered(bin_plan, breakdown, spare):
    afternoon = _second_plan(bin_plan, bin_plan.vehicle_id, at=time(15, 0))
    approved = _verify(breakdown, spare)
    assert set(approved.substituted_plan_ids) == {bin_plan.unique_id, afternoon.unique_id}


# ── S15 plan vehicle changed ──────────────────────────────────────────


def test_s15_changing_the_plan_vehicle_ends_the_substitution(bin_plan, breakdown, spare):
    _verify(breakdown, spare)
    other = VehicleCreation.objects.create(
        company_id=bin_plan.company_id, project_id=bin_plan.project_id, vehicle_no="TN01NEW",
    )
    bin_plan.vehicle_id = other.unique_id
    bin_plan.save(update_fields=["vehicle_id"])
    vehicle_substitution.end_for_plan_vehicle_change(bin_plan)

    assert not vehicle_substitution.active_substitutions().exists()
    tomorrow = _today() + timedelta(days=1)
    assert vehicle_substitution.vehicle_for_plan(bin_plan, tomorrow) == (other.unique_id, None)


# ── Deleting ──────────────────────────────────────────────────────────


def test_cascade_deleting_a_breakdown_brings_the_vehicle_back(bin_plan, breakdown):
    assert _status(bin_plan.vehicle_id) == VehicleCreation.OperationalStatus.BREAKDOWN
    cascade_soft_delete(breakdown)
    assert _status(bin_plan.vehicle_id) == VehicleCreation.OperationalStatus.ACTIVE


def test_deleting_the_trip_keeps_the_breakdown_closable(bin_plan, breakdown, source_trip):
    """The trip's cascade does not reach its breakdown, so the vehicle stays
    BREAKDOWN — and the breakdown is still there to reject or repair."""
    cascade_soft_delete(source_trip)
    breakdown.refresh_from_db()
    assert not breakdown.is_deleted
    assert _status(bin_plan.vehicle_id) == VehicleCreation.OperationalStatus.BREAKDOWN


# ── Manual trip and "Generate selected" use the replacement ───────────


def test_generate_selected_path_uses_the_replacement(bin_plan, breakdown, spare):
    from app.services.daily_trip_generation import generate_assignment_for_plan

    _verify(breakdown, spare)
    tomorrow = _today() + timedelta(days=1)
    trip, created, _ = generate_assignment_for_plan(bin_plan, tomorrow)
    assert created
    assert trip.vehicle_id == spare.unique_id


# ── Trip plan screen: add / end a replacement vehicle ─────────────────


def _plan_action(plan, action, method, data, monkeypatch):
    from rest_framework.test import APIRequestFactory

    from app.viewsets.core_modules.schedule_setup.trip_plan_viewset import TripPlanViewSet

    monkeypatch.setattr(TripPlanViewSet, "permission_classes", [])
    monkeypatch.setattr(TripPlanViewSet, "get_object", lambda self: plan)
    monkeypatch.setattr(TripPlanViewSet, "_audit_actor_id", lambda self: None)
    factory = getattr(APIRequestFactory(), method)
    request = factory(f"/trip-plans/{plan.unique_id}/x/", data, format="json")
    return TripPlanViewSet.as_view({method: action})(request, unique_id=plan.unique_id)


def test_trip_plan_substitution_warns_then_saves_on_confirm(bin_plan, breakdown, spare, monkeypatch):
    _second_plan(bin_plan, spare.unique_id)  # the spare is busy every day

    first = _plan_action(
        bin_plan, "create_vehicle_substitution", "post",
        {"replacement_vehicle_id": spare.unique_id}, monkeypatch,
    )
    assert first.status_code == 409
    assert first.data["clashes"]

    confirmed = _plan_action(
        bin_plan, "create_vehicle_substitution", "post",
        {"replacement_vehicle_id": spare.unique_id, "confirm_clashes": True}, monkeypatch,
    )
    assert confirmed.status_code == 201, confirmed.data
    assert confirmed.data["replacement_vehicle_no"] == "TN01SPARE"

    # Today's trip can now be generated on the spare.
    run_for_date(target_date=_today() + timedelta(days=1), force=True)
    assert _trips(bin_plan, _today() + timedelta(days=1)).get().vehicle_id == spare.unique_id

    ended = _plan_action(bin_plan, "end_vehicle_substitution", "post", {}, monkeypatch)
    assert ended.status_code == 200
    assert not vehicle_substitution.active_substitutions().exists()


def test_trip_plan_substitution_needs_a_broken_vehicle(bin_plan, spare, monkeypatch):
    response = _plan_action(
        bin_plan, "create_vehicle_substitution", "post",
        {"replacement_vehicle_id": spare.unique_id}, monkeypatch,
    )
    assert response.status_code == 400
