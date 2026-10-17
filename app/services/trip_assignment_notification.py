"""Tell a trip's crew that a daily trip was assigned to them.

Called from every place a daily trip is created — the supervisor app's
"Assign trip" (generate-selected), the web's manual create, and the
scheduler (web "Run scheduler" and the nightly run) — so the driver and
operators get an in-app notification plus a push whichever way it happened.

Sent after the surrounding transaction commits: a rolled-back assignment
must not leave the crew a notification for a trip that doesn't exist.
"""
import logging

from django.db import transaction

from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.staff_notification_service import notify_staff

logger = logging.getLogger(__name__)


def _crew(assignment):
    """Driver, operator and extra operators of the team running the trip —
    the substitute team when one is active, otherwise the plan's team."""
    template = assignment.alt_staff_template or assignment.staff_template
    if template is None:
        return []
    members = [template.driver, template.operator]
    extra_ids = getattr(template, "extra_operator_id", None) or []
    if extra_ids:
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        members += list(
            Staffcreation.objects.filter(
                staff_unique_id__in=extra_ids, is_deleted=False
            )
        )
    seen, crew = set(), []
    for member in members:
        if member is not None and member.staff_unique_id not in seen:
            seen.add(member.staff_unique_id)
            crew.append(member)
    return crew


def _message(assignment):
    """("New trip assigned", "Ward B · Household collection · Starts 14:30 ·
    UP16KT1912")."""
    wards = ", ".join(
        name if name.lower().startswith("ward") else f"Ward {name}"
        for name in (
            getattr(w, "ward_name", None) or str(w) for w in assignment.wards
        )
        if name
    )
    plan = assignment.trip_plan
    collection = (
        (getattr(plan, "collection_type", "") or "")
        .replace("_", " ")
        .strip()
        .capitalize()
    )
    time = (
        assignment.scheduled_time.strftime("%H:%M")
        if assignment.scheduled_time
        else ""
    )
    vehicle = getattr(assignment.vehicle, "vehicle_no", None)
    parts = [
        wards or getattr(plan, "display_code", None),
        collection,
        f"Starts {time}" if time else "",
        vehicle,
    ]
    return "New trip assigned", " · ".join(p for p in parts if p)


def notify_trip_assigned(assignment):
    """Queue the notification for after commit; never raises."""

    def _send():
        try:
            title, body = _message(assignment)
            data = {
                "trip_assignment_id": str(assignment.unique_id),
                "trip_date": str(assignment.trip_date),
            }
            for member in _crew(assignment):
                notify_staff(
                    member,
                    StaffNotification.TYPE_TRIP_ASSIGNED,
                    title,
                    body,
                    data=data,
                )
        except Exception:
            logger.exception(
                "Failed to notify crew of trip %s",
                getattr(assignment, "unique_id", assignment),
            )

    transaction.on_commit(_send)
