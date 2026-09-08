"""Hierarchy-driven auto-escalation for complaint tickets.

A ticket starts at whichever hierarchy level is the SLA rule's lowest
*enabled* `ComplaintSlaEscalationLevel` (see `complaint_ticket_routing.
_entry_level_number`) — a project's hierarchy may include Driver/Operator/
Supervisor/Project Admin/Company Admin, but a rule can disable the lower
ones so tickets start at Supervisor instead. If it isn't resolved by
`next_escalation_due_at`, it hops to the next *enabled* level above it in
that project's `ProjectStaffHierarchy` — disabled levels are skipped
entirely, not just as an entry point but as hop targets too. Reaching the
top of the hierarchy (or running out of enabled levels above the current
one) simply stops escalating.

At each level, which staff member the ticket actually goes to is narrowed by
geography (see `complaint_ticket_routing._staff_for_hierarchy_level`) — a
Supervisor scoped to certain zones/wards only receives tickets from those
areas, not every ticket at that hierarchy level project-wide.
"""
from django.db import transaction
from django.utils import timezone

from app.services.complaint_ticket_routing import _add_business_minutes, _entry_level_number


def compute_next_due(minutes, working_hours_only):
    """Deadline `minutes` from now, honoring the SLA rule's business-hours flag."""
    if minutes is None:
        return None
    if working_hours_only:
        return _add_business_minutes(timezone.now(), minutes)
    from datetime import timedelta
    return timezone.now() + timedelta(minutes=minutes)


def _resolve_window_minutes(ticket, level):
    """Resolve-within minutes configured for `level` under ticket's SLA rule,
    or (None, sla_rule) if that level has no configured window."""
    from app.services.complaint_ticket_routing import _best_sla_rule

    sla_rule = _best_sla_rule(ticket)
    if not sla_rule:
        return None, None

    level_row = sla_rule.escalation_levels.filter(level=level, is_deleted=False).first()
    if level_row:
        return level_row.resolve_within_minutes, sla_rule

    return None, sla_rule


def _enabled_levels_above(ticket, current_level):
    """Enabled `ComplaintSlaEscalationLevel.level` numbers above
    `current_level` for the ticket's best-matching SLA rule, ascending."""
    from app.services.complaint_ticket_routing import _best_sla_rule

    sla_rule = _best_sla_rule(ticket)
    if not sla_rule:
        return []

    return list(
        sla_rule.escalation_levels.filter(
            is_enabled=True, is_deleted=False, level__gt=current_level,
        )
        .order_by("level")
        .values_list("level", flat=True)
    )


def get_next_level_staff(ticket):
    """Return (next_level_num, staff) for the next *enabled* escalation level
    above `ticket.escalation_level` whose staff's geo grants cover this
    ticket, or (None, None) if there is no such level (chain exhausted, none
    configured, or nobody at the remaining levels covers this ticket's
    zone/panchayat/ward).
    """
    from app.services.complaint_ticket_routing import _staff_for_hierarchy_level

    for level_num in _enabled_levels_above(ticket, ticket.escalation_level):
        staff = _staff_for_hierarchy_level(ticket.project_id, level_num, ticket)
        if staff:
            return level_num, staff
    return None, None


@transaction.atomic
def escalate_ticket(ticket, reason=None, escalated_by=None, by_system=True):
    """Escalate `ticket` to the next enabled hierarchy level above its
    current one.

    Locks the ticket row (`select_for_update`) so two concurrent callers
    (a Celery/cron sweep and a manual action) can't double-escalate the same
    ticket. Raises ValueError if there is no next enabled level to escalate to.
    """
    from app.models.complaint_management.masters import ComplaintStatus
    from app.models.complaint_management.transactions import (
        ComplaintEscalationHistory,
        ComplaintStatusHistory,
    )
    from app.models.complaint_management.ticket import ComplaintTicket
    from app.models.notifications.staff_notification import StaffNotification
    from app.services.push_notification_service import send_push_to_customer
    from app.services.staff_notification_service import notify_staff

    ticket = ComplaintTicket.objects.select_for_update().get(pk=ticket.pk)

    to_level, next_staff = get_next_level_staff(ticket)
    if next_staff is None:
        raise ValueError("No further escalation level configured for this ticket.")

    from_level = ticket.escalation_level
    from_staff = ticket.escalated_to_staff or ticket.assigned_staff

    ticket.escalation_level = to_level
    ticket.is_escalated = True
    ticket.escalated_to_staff = next_staff

    minutes, sla_rule = _resolve_window_minutes(ticket, to_level)
    working_hours_only = sla_rule.working_hours_only if sla_rule else False
    ticket.next_escalation_due_at = compute_next_due(minutes, working_hours_only)

    update_fields = [
        "escalation_level",
        "is_escalated",
        "escalated_to_staff",
        "next_escalation_due_at",
    ]

    old_status = ticket.status
    escalated_status = ComplaintStatus.objects.filter(status_code="ESCALATED", is_deleted=False).first()
    if escalated_status:
        ticket.status = escalated_status
        update_fields.append("status")

    ticket.save(update_fields=update_fields)

    ComplaintEscalationHistory.objects.create(
        ticket=ticket,
        escalation_level=to_level,
        escalated_to_staff=next_staff,
        reason=reason,
        escalated_by_system=by_system,
    )

    if escalated_status:
        from_label = f"L{from_level}" + (f" - {from_staff.employee_name}" if from_staff else "")
        to_label = f"L{to_level} - {next_staff.employee_name}"
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=old_status,
            to_status=escalated_status,
            changed_by_user=escalated_by,
            changed_by_system=by_system,
            remarks=f"Auto-escalated {from_label} -> {to_label}"
            + (f": {reason}" if reason else ""),
            visible_to_citizen=True,
        )

    notify_staff(
        next_staff,
        StaffNotification.TYPE_TICKET_ESCALATED_TO,
        "Ticket escalated to you",
        f"Ticket {ticket.ticket_no} escalated to you"
        + (f" from {from_staff.employee_name}" if from_staff else "")
        + (f". Reason: {reason}" if reason else "."),
        data={"event": "ticket_escalated_to", "ticket_id": str(ticket.unique_id)},
    )

    if ticket.customer_id:
        send_push_to_customer(
            ticket.customer,
            "Your complaint has been escalated",
            f"Ticket {ticket.ticket_no} has been escalated to ensure faster resolution.",
            data={"event": "ticket_escalated", "ticket_id": str(ticket.unique_id)},
        )

    return ticket


def check_and_escalate_overdue_tickets():
    """Sweep overdue tickets and escalate each one hop. Called by the
    `escalate_overdue_complaint_tickets` management command (run on a
    schedule via cron)."""
    from app.models.complaint_management.ticket import ComplaintTicket

    now = timezone.now()

    overdue = ComplaintTicket.objects.filter(
        next_escalation_due_at__lt=now,
        status__is_final=False,
        is_deleted=False,
    ).select_related("category", "priority", "project_id", "company_id", "assigned_staff", "escalated_to_staff")

    count = 0
    for ticket in overdue:
        try:
            escalate_ticket(ticket, reason="SLA breach - auto escalation", by_system=True)
            count += 1
        except ValueError:
            # No further enabled level configured for this project/ticket —
            # clear the due date so the sweep stops picking it up every run.
            ticket.next_escalation_due_at = None
            ticket.save(update_fields=["next_escalation_due_at"])

    return count


def set_initial_escalation_due_date(ticket, save=False):
    """Set `escalation_level` to the SLA rule's lowest enabled level and its
    `next_escalation_due_at` on a newly created ticket. Called from
    `apply_routing_and_sla` so every ticket creation path gets this without
    duplicating the lookup at each call site.
    """
    entry_level = _entry_level_number(ticket)
    ticket.escalation_level = entry_level
    minutes, sla_rule = _resolve_window_minutes(ticket, entry_level)
    working_hours_only = sla_rule.working_hours_only if sla_rule else False
    ticket.next_escalation_due_at = compute_next_due(minutes, working_hours_only)

    if save:
        ticket.save(update_fields=["escalation_level", "next_escalation_due_at"])

    return ticket
