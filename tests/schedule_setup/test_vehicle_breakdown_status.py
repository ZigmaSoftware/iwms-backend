from datetime import time, timedelta

import pytest
from django.utils import timezone
from rest_framework import serializers

from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.vehicle_breakdown import (
    VehicleBreakdown,
    sync_vehicle_operational_status,
)
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
    VehicleBreakdownMarkRepairedSerializer,
    VehicleBreakdownRejectSerializer,
    _ensure_vehicle_in_service,
)

pytestmark = pytest.mark.django_db

ACTIVE = VehicleCreation.OperationalStatus.ACTIVE
BREAKDOWN = VehicleCreation.OperationalStatus.BREAKDOWN


def _breakdown(plan, **extra):
    assignment = DailyTripAssignment.objects.create(
        company_id=plan.company_id,
        project_id=plan.project_id,
        trip_plan_id=plan.unique_id,
        staff_template_id=plan.staff_template_id,
        vehicle_id=plan.vehicle_id,
        panchayat_id=plan.panchayat_id,
        waste_type_ids=plan.waste_type_ids,
        trip_date=timezone.localdate(),
        scheduled_time=time(9, 0),
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
    )
    breakdown = VehicleBreakdown.objects.create(
        company_id=plan.company_id,
        project_id=plan.project_id,
        trip_assignment_id=assignment.unique_id,
        breakdown_vehicle_id=plan.vehicle_id,
        **extra,
    )
    sync_vehicle_operational_status(plan.vehicle_id)
    return breakdown


def _status(vehicle_id):
    return VehicleCreation.objects.get(unique_id=vehicle_id).operational_status


def test_reported_breakdown_marks_vehicle_breakdown(bin_plan):
    _breakdown(bin_plan)
    assert _status(bin_plan.vehicle_id) == BREAKDOWN


def test_rejected_breakdown_returns_vehicle_to_active(bin_plan):
    breakdown = _breakdown(bin_plan)
    serializer = VehicleBreakdownRejectSerializer(
        data={"rejection_remarks": "Tyre fixed on the spot"},
        context={"instance": breakdown},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    assert _status(bin_plan.vehicle_id) == ACTIVE


def test_mark_repaired_returns_vehicle_to_active(bin_plan):
    breakdown = _breakdown(bin_plan, approval_status=VehicleBreakdown.APPROVAL_APPROVED)
    serializer = VehicleBreakdownMarkRepairedSerializer(
        data={"repair_remarks": "Engine replaced"},
        context={"instance": breakdown},
    )
    serializer.is_valid(raise_exception=True)
    breakdown = serializer.save()

    assert breakdown.repaired_at is not None
    assert breakdown.repair_remarks == "Engine replaced"
    assert _status(bin_plan.vehicle_id) == ACTIVE

    again = VehicleBreakdownMarkRepairedSerializer(data={}, context={"instance": breakdown})
    again.is_valid(raise_exception=True)
    with pytest.raises(serializers.ValidationError):
        again.save()


def test_pending_breakdown_cannot_be_marked_repaired(bin_plan):
    breakdown = _breakdown(bin_plan)
    serializer = VehicleBreakdownMarkRepairedSerializer(
        data={}, context={"instance": breakdown},
    )
    serializer.is_valid(raise_exception=True)
    with pytest.raises(serializers.ValidationError):
        serializer.save()
    assert _status(bin_plan.vehicle_id) == BREAKDOWN


def test_vehicle_stays_breakdown_while_another_breakdown_is_open(bin_plan):
    first = _breakdown(bin_plan, approval_status=VehicleBreakdown.APPROVAL_APPROVED)
    _breakdown(bin_plan)

    serializer = VehicleBreakdownMarkRepairedSerializer(
        data={}, context={"instance": first},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    assert _status(bin_plan.vehicle_id) == BREAKDOWN


def test_broken_down_vehicle_cannot_be_replacement(bin_plan):
    _breakdown(bin_plan)
    with pytest.raises(serializers.ValidationError):
        _ensure_vehicle_in_service(bin_plan.vehicle_id)


def _set_status(vehicle_id, status):
    VehicleCreation.objects.filter(unique_id=vehicle_id).update(operational_status=status)


def test_daily_generation_skips_plan_whose_vehicle_is_under_breakdown(bin_plan):
    from app.management.commands.generate_daily_trips import run_for_date

    _set_status(bin_plan.vehicle_id, BREAKDOWN)
    summary = run_for_date(force=True)

    assert summary["skipped_breakdown"] == [{
        "trip_plan_id": bin_plan.unique_id,
        "vehicle_id": bin_plan.vehicle_id,
        "reason": "Vehicle is under breakdown and no replacement vehicle is set",
    }]
    assert not DailyTripAssignment.objects.filter(trip_plan_id=bin_plan.unique_id).exists()

    _set_status(bin_plan.vehicle_id, ACTIVE)
    run_for_date(force=True)
    assert DailyTripAssignment.objects.filter(trip_plan_id=bin_plan.unique_id).exists()


def test_retrip_cannot_continue_on_broken_down_vehicle(bin_plan, supervisor):
    from app.services import retrip_service

    breakdown = _breakdown(bin_plan)
    request = retrip_service.request_retrip(
        breakdown.trip_assignment, requested_by=supervisor, reason="Vehicle stopped",
    )
    with pytest.raises(ValueError, match="under breakdown"):
        retrip_service.approve_retrip(request, reviewed_by=supervisor)


def test_manual_trip_cannot_use_broken_down_vehicle(bin_plan, ward):
    from app.serializers.core_modules.daily_operations.daily_trip_assignment_serializer import (
        DailyTripAssignmentSerializer,
    )

    _set_status(bin_plan.vehicle_id, BREAKDOWN)
    serializer = DailyTripAssignmentSerializer(data={
        "trip_plan_id": bin_plan.unique_id,
        "trip_date": timezone.localdate().isoformat(),
        "scheduled_time": "06:00",
        "ward_ids": [ward.unique_id],
    })
    assert not serializer.is_valid()
    assert "vehicle_id" in serializer.errors


# ── Other trips of the broken vehicle ─────────────────────────────────


def _trip(plan, *, vehicle_id=None, days=0, at=time(11, 0)):
    return DailyTripAssignment.objects.create(
        company_id=plan.company_id,
        project_id=plan.project_id,
        trip_plan_id=plan.unique_id,
        staff_template_id=plan.staff_template_id,
        vehicle_id=vehicle_id or plan.vehicle_id,
        panchayat_id=plan.panchayat_id,
        waste_type_ids=plan.waste_type_ids,
        trip_date=timezone.localdate() + timedelta(days=days),
        scheduled_time=at,
        status=DailyTripAssignment.STATUS_SCHEDULED,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
    )


def _verify(breakdown, replacement, driver, operator, **extra):
    from types import SimpleNamespace

    from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
        VehicleBreakdownVerifySerializer,
    )

    serializer = VehicleBreakdownVerifySerializer(
        data={
            "replacement_vehicle_id": replacement.unique_id,
            "replacement_driver_id": driver.staff_unique_id,
            "replacement_operator_id": operator.staff_unique_id,
            **extra,
        },
        context={
            "instance": breakdown,
            "request": SimpleNamespace(user=SimpleNamespace(staffusertype=None)),
            "account": None,
        },
    )
    assert serializer.is_valid(), serializer.errors
    return serializer.save()


@pytest.fixture
def replacement(bin_plan):
    return VehicleCreation.objects.create(
        company_id=bin_plan.company_id, project_id=bin_plan.project_id, vehicle_no="TN01SPARE",
    )


def test_verify_moves_only_the_ticked_trips(bin_plan, bin_stop, replacement, driver, operator):
    breakdown = _breakdown(bin_plan)
    later_today = _trip(bin_plan, at=time(14, 0))
    tomorrow = _trip(bin_plan, days=1)

    approved = _verify(
        breakdown, replacement, driver, operator,
        move_assignment_ids=[later_today.unique_id, tomorrow.unique_id],
    )

    for trip in (later_today, tomorrow):
        trip.refresh_from_db()
        assert trip.vehicle_id == replacement.unique_id
        assert trip.staff_template_id == bin_plan.staff_template_id
    assert set(approved.moved_assignment_ids) == {later_today.unique_id, tomorrow.unique_id}


def test_verify_without_a_selection_moves_nothing(bin_plan, bin_stop, replacement, driver, operator):
    """The mobile sheet has no picker: trips stay flagged on the broken vehicle."""
    breakdown = _breakdown(bin_plan)
    later_today = _trip(bin_plan, at=time(14, 0))

    approved = _verify(breakdown, replacement, driver, operator)

    later_today.refresh_from_db()
    assert later_today.vehicle_id == bin_plan.vehicle_id
    assert later_today.blocked_by_vehicle_breakdown()
    assert approved.moved_assignment_ids == []


def test_unticked_trip_stays_blocked_until_repair(bin_plan, bin_stop, replacement, driver, operator):
    from app.serializers.core_modules.daily_operations.daily_trip_assignment_serializer import (
        DailyTripAssignmentSerializer,
    )

    breakdown = _breakdown(bin_plan)
    moved = _trip(bin_plan, at=time(14, 0))
    kept = _trip(bin_plan, at=time(16, 0))

    approved = _verify(
        breakdown, replacement, driver, operator, move_assignment_ids=[moved.unique_id],
    )
    kept.refresh_from_db()
    assert kept.vehicle_id == bin_plan.vehicle_id
    assert kept.blocked_by_vehicle_breakdown()
    assert DailyTripAssignmentSerializer(kept).data["vehicle_under_breakdown"] is True

    repaired = VehicleBreakdownMarkRepairedSerializer(data={}, context={"instance": approved})
    repaired.is_valid(raise_exception=True)
    repaired.save()
    kept = DailyTripAssignment.objects.get(pk=kept.pk)
    assert not kept.blocked_by_vehicle_breakdown()
    assert DailyTripAssignmentSerializer(kept).data["vehicle_under_breakdown"] is False


def test_trip_not_moved_when_replacement_is_booked_at_that_time(
    bin_plan, bin_stop, replacement, driver, operator,
):
    breakdown = _breakdown(bin_plan)
    trip = _trip(bin_plan, at=time(14, 0))
    # The spare's own job, with its own crew, at the same time.
    DailyTripAssignment.objects.filter(
        pk=_trip(bin_plan, vehicle_id=replacement.unique_id, at=time(14, 0)).pk,
    ).update(staff_template_id=None)

    approved = _verify(
        breakdown, replacement, driver, operator, move_assignment_ids=[trip.unique_id],
    )

    trip.refresh_from_db()
    assert trip.vehicle_id == bin_plan.vehicle_id
    assert approved.moved_assignment_ids == []
    assert [s["trip_id"] for s in approved.skipped_moves] == [trip.unique_id]


def test_running_trip_is_not_blocked(bin_plan):
    breakdown = _breakdown(bin_plan)
    assert not breakdown.trip_assignment.blocked_by_vehicle_breakdown()


def test_driver_cannot_start_trip_on_broken_down_vehicle(bin_plan, monkeypatch):
    from rest_framework.test import APIRequestFactory

    from app.viewsets.operator_mobile.trip_lifecycle_viewset import TripLifecycleViewSet

    _breakdown(bin_plan)
    trip = _trip(bin_plan, at=time(14, 0))
    monkeypatch.setattr(TripLifecycleViewSet, "permission_classes", [])
    monkeypatch.setattr(
        TripLifecycleViewSet, "_resolve_own_assignment", lambda self, request, pk: (None, trip),
    )

    request = APIRequestFactory().post(f"/trip-lifecycle/{trip.unique_id}/start/")
    response = TripLifecycleViewSet.as_view({"post": "start"})(request, pk=trip.unique_id)

    assert response.status_code == 409
    assert response.data["code"] == "VEHICLE_BREAKDOWN"
    trip.refresh_from_db()
    assert trip.status == DailyTripAssignment.STATUS_SCHEDULED


def _change_vehicle(trip, vehicle_id, monkeypatch):
    from rest_framework.test import APIRequestFactory

    from app.viewsets.core_modules.daily_operations.daily_trip_assignment_viewset import (
        DailyTripAssignmentViewSet,
    )

    monkeypatch.setattr(DailyTripAssignmentViewSet, "permission_classes", [])
    monkeypatch.setattr(DailyTripAssignmentViewSet, "get_object", lambda self: trip)
    monkeypatch.setattr(DailyTripAssignmentViewSet, "log_audit", lambda self, *a, **k: None)
    request = APIRequestFactory().patch(
        f"/daily-trip-assignments/{trip.unique_id}/change-vehicle/",
        {"vehicle_id": vehicle_id},
        format="json",
    )
    return DailyTripAssignmentViewSet.as_view({"patch": "change_vehicle"})(
        request, unique_id=trip.unique_id,
    )


def test_flagged_trip_can_change_to_another_vehicle(bin_plan, replacement, monkeypatch):
    _breakdown(bin_plan)
    trip = _trip(bin_plan, at=time(14, 0))

    response = _change_vehicle(trip, replacement.unique_id, monkeypatch)

    assert response.status_code == 200, response.data
    trip.refresh_from_db()
    assert trip.vehicle_id == replacement.unique_id
    assert not trip.blocked_by_vehicle_breakdown()
    assert response.data["vehicle_under_breakdown"] is False


def test_change_vehicle_refuses_broken_down_or_booked_vehicle(bin_plan, replacement, monkeypatch):
    trip = _trip(bin_plan, at=time(14, 0))
    _set_status(replacement.unique_id, BREAKDOWN)
    assert _change_vehicle(trip, replacement.unique_id, monkeypatch).status_code == 400

    _set_status(replacement.unique_id, ACTIVE)
    DailyTripAssignment.objects.filter(
        pk=_trip(bin_plan, vehicle_id=replacement.unique_id, at=time(14, 0)).pk,
    ).update(staff_template_id=None)
    response = _change_vehicle(trip, replacement.unique_id, monkeypatch)
    assert response.status_code == 400
    assert "already has trip" in str(response.data["vehicle_id"])
