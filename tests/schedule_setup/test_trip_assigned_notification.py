"""The crew hears about a newly assigned daily trip — in-app and push —
whichever path created it, and only once."""
from datetime import date
from unittest import mock

import pytest

from app.management.commands.generate_daily_trips import run_for_date
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.daily_trip_generation import generate_assignment_for_plan

SERVICE_DATE = date(2026, 8, 3)


def _assigned(staff):
    return StaffNotification.objects.filter(
        recipient_staff_id=staff.staff_unique_id,
        notification_type=StaffNotification.TYPE_TRIP_ASSIGNED,
    )


@pytest.fixture(autouse=True)
def _no_real_push():
    with mock.patch(
        "app.services.staff_notification_service.send_push_to_staff"
    ) as push:
        yield push


@pytest.mark.django_db
def test_assign_trip_notifies_driver_and_operator(
    bin_stop, driver, operator, django_capture_on_commit_callbacks, _no_real_push
):
    with django_capture_on_commit_callbacks(execute=True):
        assignment, created, _ = generate_assignment_for_plan(
            bin_stop.trip_plan, SERVICE_DATE
        )

    assert created
    note = _assigned(driver).get()
    assert note.title == "New trip assigned"
    assert note.data["trip_assignment_id"] == assignment.unique_id
    assert _assigned(operator).count() == 1
    assert _no_real_push.call_count == 2


@pytest.mark.django_db
def test_existing_trip_is_not_announced_again(
    bin_stop, driver, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        generate_assignment_for_plan(bin_stop.trip_plan, SERVICE_DATE)
        generate_assignment_for_plan(bin_stop.trip_plan, SERVICE_DATE)

    assert _assigned(driver).count() == 1


@pytest.mark.django_db
def test_scheduler_run_notifies_driver(
    bin_stop, driver, django_capture_on_commit_callbacks
):
    plan = bin_stop.trip_plan
    plan.repeat_days = [0, 1, 2, 3, 4, 5, 6]
    plan.save(update_fields=["repeat_days"])

    with django_capture_on_commit_callbacks(execute=True):
        summary = run_for_date(target_date=SERVICE_DATE)

    assert summary["created"] == 1
    assert _assigned(driver).count() == 1
