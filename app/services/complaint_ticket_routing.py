"""Routing + SLA resolution for complaint tickets.

Ported from the government backend's `app/utils/complaint_ticket_routing.py`.
Given a ticket's category/subcategory/flat geo (state/district/panchayat/
zone/ward)/priority/source, finds the most specific matching
`ComplaintRoutingRule` (to assign a department/user) and the most specific
matching `ComplaintSlaRule` (to compute due dates), then fills only the
ticket fields that are still empty — an explicit assignment or a manually
set due date is never overwritten.

Geo scope differs from government: this project has no Corporation/
Municipality/TownPanchayat/PanchayatUnion local-body hierarchy, so
`ROUTING_GEO_ATTNAMES` uses state/district/panchayat/zone/ward instead.
"""
from datetime import timedelta, time

from django.db import models
from django.utils import timezone

BUSINESS_START = time(9, 0)
BUSINESS_END = time(18, 0)
BUSINESS_WEEKDAY_LIMIT = 6  # Monday=0 ... Saturday=5 are working days, Sunday=6 is off


def _add_business_minutes(start, minutes):
    """Add `minutes` to `start`, counting only 09:00-18:00 on Mon-Sat."""
    remaining = minutes
    current = start
    # Move into the next open window if we start outside business hours.
    while current.time() < BUSINESS_START or current.time() >= BUSINESS_END or current.weekday() > BUSINESS_WEEKDAY_LIMIT:
        if current.weekday() > BUSINESS_WEEKDAY_LIMIT or current.time() >= BUSINESS_END:
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START.hour, minute=BUSINESS_START.minute, second=0, microsecond=0
            )
        else:
            current = current.replace(
                hour=BUSINESS_START.hour, minute=BUSINESS_START.minute, second=0, microsecond=0
            )

    while remaining > 0:
        end_of_day = current.replace(hour=BUSINESS_END.hour, minute=BUSINESS_END.minute, second=0, microsecond=0)
        minutes_left_today = int((end_of_day - current).total_seconds() // 60)
        if remaining <= minutes_left_today:
            current += timedelta(minutes=remaining)
            remaining = 0
        else:
            remaining -= minutes_left_today
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START.hour, minute=BUSINESS_START.minute, second=0, microsecond=0
            )
            while current.weekday() > BUSINESS_WEEKDAY_LIMIT:
                current += timedelta(days=1)
    return current


# Flat geo FK attnames shared by ComplaintRoutingRule and ComplaintTicket.
# An empty rule field means "any"; a set field must match the ticket exactly.
ROUTING_GEO_ATTNAMES = (
    "state_id",
    "district_id",
    "panchayat_id",
    "zone_id",
    "ward_id",
)

# A ticket in one of these statuses is done — it doesn't count toward a
# staff member's load and won't be picked up as "the next queued ticket".
# Matches the "resolved"/"open" buckets in `ticket_viewset._status_bucket_q`;
# keep the two in sync.
CLOSED_STATUS_CODES = ("RESOLVED", "CLOSED", "REJECTED", "CANCELLED")


def _routing_matches(rule, ticket):
    if rule.subcategory_id and rule.subcategory_id != ticket.subcategory_id:
        return False
    for attname in ROUTING_GEO_ATTNAMES:
        rule_value = getattr(rule, attname, None)
        if rule_value and rule_value != getattr(ticket, attname, None):
            return False
    if rule.priority_id and rule.priority_id != ticket.priority_id:
        return False
    return True


def _routing_specificity(rule):
    return sum([
        bool(rule.subcategory_id),
        bool(rule.priority_id),
        *[bool(getattr(rule, attname, None)) for attname in ROUTING_GEO_ATTNAMES],
    ])


def _best_routing_rule(ticket):
    from app.models.complaint_management.transactions import ComplaintRoutingRule

    candidates = ComplaintRoutingRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category_id=ticket.category_id,
    ).select_related("department", "user", "sla_rule")

    matching = [rule for rule in candidates if _routing_matches(rule, ticket)]
    if not matching:
        return None
    matching.sort(key=_routing_specificity, reverse=True)
    return matching[0]


def _sla_matches(rule, ticket):
    if rule.subcategory_id and rule.subcategory_id != ticket.subcategory_id:
        return False
    if rule.priority_id and rule.priority_id != ticket.priority_id:
        return False
    if rule.source_id and rule.source_id != ticket.source_id:
        return False
    return True


def _sla_specificity(rule):
    return sum([
        bool(rule.subcategory_id),
        bool(rule.priority_id),
        bool(rule.source_id),
    ])


def _pick_least_loaded_staff(department):
    """Return the active, non-supervisor department member with the fewest
    open tickets, or None if the department has no eligible members.

    Ties break on `unique_id` so the pick is deterministic (and testable)
    rather than depending on incidental row order.
    """
    from app.models.complaint_management.masters import ComplaintDepartmentMember

    members = (
        ComplaintDepartmentMember.objects.filter(
            department=department,
            is_supervisor=False,
            is_active=True,
            is_deleted=False,
        )
        .select_related("staff")
        .annotate(
            open_count=models.Count(
                "staff__assigned_complaint_tickets_staff",
                filter=~models.Q(
                    staff__assigned_complaint_tickets_staff__status__status_code__in=CLOSED_STATUS_CODES
                )
                & models.Q(staff__assigned_complaint_tickets_staff__is_deleted=False),
                distinct=True,
            )
        )
        .order_by("open_count", "unique_id")
    )
    first = members.first()
    return first.staff if first else None


def _best_sla_rule(ticket):
    from app.models.complaint_management.masters import ComplaintSlaRule

    candidates = ComplaintSlaRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category_id=ticket.category_id,
    )

    matching = [rule for rule in candidates if _sla_matches(rule, ticket)]
    if not matching:
        return None
    matching.sort(key=_sla_specificity, reverse=True)
    return matching[0]


def apply_routing_and_sla(ticket, save=True):
    """Fill department/assigned_staff and sla_due_at/first_response_due_at
    on `ticket` from the best-matching routing + SLA rules — only touching
    fields that are currently empty. Returns the list of updated field names.
    """
    updated_fields = []
    now = timezone.now()

    # Department-based routing + load-balanced individual assignment: a
    # ticket is routed to a `Department`, then handed to whichever active
    # member of that department currently has the fewest open tickets.
    routing_rule = None
    if not ticket.department_id:
        routing_rule = _best_routing_rule(ticket)
        department = None
        if routing_rule and routing_rule.department_id:
            department = routing_rule.department
        elif ticket.category_id and ticket.category.default_department_id:
            # No routing rule matched — fall back to the category's default
            # department. A deployment only needs rules when a category must
            # route differently by area.
            department = ticket.category.default_department

        if department:
            ticket.department = department
            updated_fields.append("department")
            if not ticket.assigned_staff_id:
                staff = _pick_least_loaded_staff(department)
                if staff:
                    ticket.assigned_staff = staff
                    updated_fields.append("assigned_staff")

    # Prefer the most specific SLA rule that actually matches this ticket over
    # the one pinned on the routing rule.
    #
    # A routing rule's `sla_rule` is a catch-all: the seeder attaches the
    # category-wide rule to a category-wide route. Taking it unconditionally
    # meant a ticket whose sub-category has its own SLA (a P1 "Dead animal"
    # under a P2 Garbage category) silently got the category's slower target —
    # 24h instead of 4h — because the pinned rule was consulted first and
    # `_best_sla_rule` never ran. The pinned rule is now the fallback for when
    # nothing more specific matches.
    sla_rule = _best_sla_rule(ticket)
    if not sla_rule and routing_rule and routing_rule.sla_rule_id:
        sla_rule = routing_rule.sla_rule

    if sla_rule:
        add_minutes = _add_business_minutes if sla_rule.working_hours_only else (
            lambda start, minutes: start + timedelta(minutes=minutes)
        )
        if not ticket.first_response_due_at and sla_rule.assign_within_minutes:
            ticket.first_response_due_at = add_minutes(now, sla_rule.assign_within_minutes)
            updated_fields.append("first_response_due_at")
        if not ticket.sla_due_at and sla_rule.resolve_within_minutes:
            ticket.sla_due_at = add_minutes(now, sla_rule.resolve_within_minutes)
            updated_fields.append("sla_due_at")

    if save and updated_fields:
        ticket.save(update_fields=updated_fields)

    return updated_fields


def perform_escalation(ticket, reason=None, actor_user=None, by_system=False):
    """Escalate `ticket` to its department's supervisor.

    The ticket's single supervisor is looked up from
    `ComplaintDepartmentMember` and notified. `assigned_staff` is
    deliberately left unchanged — the member who owns the ticket keeps it
    (and it keeps counting toward their open-ticket load for round-robin
    purposes); the ticket becomes additionally visible to the supervisor via
    `is_escalated`/`escalated_to_staff`. This is what lets an escalated
    ticket stay visible to both the member and the supervisor.

    Shared by the manual `/escalate/` API action and any future automated
    SLA-breach detection job so both paths write identical history rows.
    Raises ValueError if the ticket has no department, or the department has
    no supervisor configured.
    """
    from app.models.complaint_management.masters import ComplaintDepartmentMember, ComplaintStatus
    from app.models.complaint_management.transactions import (
        ComplaintEscalationHistory,
        ComplaintStatusHistory,
    )
    from app.services.staff_notification_service import notify_staff
    from app.models.notifications.staff_notification import StaffNotification

    if not ticket.department_id:
        raise ValueError("Ticket has no department to escalate within.")

    escalated_status = ComplaintStatus.objects.filter(status_code="ESCALATED", is_deleted=False).first()
    old_status = ticket.status

    supervisor_member = (
        ComplaintDepartmentMember.objects.filter(
            department_id=ticket.department_id,
            is_supervisor=True,
            is_active=True,
            is_deleted=False,
        )
        .select_related("staff")
        .first()
    )
    if not supervisor_member:
        raise ValueError("No supervisor configured for this department.")
    supervisor = supervisor_member.staff
    from_staff = ticket.assigned_staff

    ticket.is_escalated = True
    ticket.escalated_to_staff = supervisor
    update_fields = ["is_escalated", "escalated_to_staff"]
    if escalated_status:
        ticket.status = escalated_status
        update_fields.append("status")
    ticket.save(update_fields=update_fields)

    escalation = ComplaintEscalationHistory.objects.create(
        ticket=ticket,
        escalation_level=1,
        escalated_to_staff=supervisor,
        reason=reason,
        escalated_by_system=by_system,
    )
    # No ComplaintAssignmentHistory row: assigned_staff did not change, so
    # an "assignment" entry here would misrepresent this as a handoff.
    if escalated_status:
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=old_status,
            to_status=escalated_status,
            changed_by_user=actor_user,
            changed_by_system=by_system,
            remarks=f"Escalated to supervisor {supervisor.employee_name}" + (f": {reason}" if reason else ""),
            visible_to_citizen=True,
        )
    notify_staff(
        supervisor,
        StaffNotification.TYPE_TICKET_ESCALATED_TO,
        "Ticket escalated to you",
        f"Ticket {ticket.ticket_no} escalated to you by "
        f"{getattr(from_staff, 'employee_name', 'a member')}." + (
            f" Reason: {reason}" if reason else ""
        ),
        data={"event": "ticket_escalated_to", "ticket_id": str(ticket.unique_id)},
    )
    return escalation


def backfill_department_queue(department, save=True):
    """After a ticket in `department` frees capacity (resolved/closed/etc.),
    auto-assign the oldest unassigned ticket in that department's queue to
    the now-least-loaded member — the "real-time" part of customer-care
    assignment: freed capacity doesn't sit idle.

    Returns the ticket that was assigned, or None if there was no queued
    ticket or no eligible member to give it to.
    """
    from app.models.complaint_management.ticket import ComplaintTicket

    next_ticket = (
        ComplaintTicket.objects.filter(
            department=department,
            assigned_staff__isnull=True,
            is_deleted=False,
        )
        .exclude(status__status_code__in=CLOSED_STATUS_CODES)
        .order_by("created")
        .first()
    )
    if not next_ticket:
        return None
    staff = _pick_least_loaded_staff(department)
    if not staff:
        return None
    next_ticket.assigned_staff = staff
    if save:
        next_ticket.save(update_fields=["assigned_staff"])
    return next_ticket
