"""Assignment + SLA resolution for complaint tickets.

A new ticket is assigned to whoever holds level 0 of its project's staff
hierarchy (`ProjectStaffHierarchy` + `StaffUserType`) — there is no
department roster or load-balancing step. Multiple staff can hold the same
hierarchy level in a project (e.g. a Supervisor per zone); which one a given
ticket goes to is narrowed by geography via `StaffAccessConfiguration`
(zones/panchayats/wards), using the same "narrowest non-empty grant wins,
empty means unrestricted" rule as `LocationScopedViewSetMixin` elsewhere in
this app. If nobody at that level covers the ticket's zone/panchayat/ward,
the ticket is left unassigned rather than guessed at.

SLA due dates still come from `ComplaintSlaRule`/`ComplaintRoutingRule`
(geo/category/priority matching) — that part is unrelated to who the ticket
is assigned to.
"""
from datetime import timedelta, time

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
    """Best-matching `ComplaintRoutingRule` for this ticket, used only to
    pin a specific SLA rule by geo/category/priority — it no longer carries
    a department."""
    from app.models.complaint_management.transactions import ComplaintRoutingRule

    candidates = ComplaintRoutingRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category_id=ticket.category_id,
    ).select_related("sla_rule")

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


def _staff_geo_matches(staff, ticket):
    """Whether `staff`'s `StaffAccessConfiguration` geo grants cover
    `ticket`'s zone/panchayat/ward, using the same "narrowest non-empty
    grant wins, empty means unrestricted at that level" rule as
    `LocationScopedViewSetMixin`. A staff member with no access
    configuration row at all (or none of the three grants populated) is
    treated as unrestricted, so existing single-zone deployments that never
    configured Data Scope keep working unchanged.
    """
    access_config = staff.access_configuration.filter(
        is_active=True, is_deleted=False,
    ).first()
    if not access_config:
        return True

    if ticket.ward_id:
        wards = access_config.wards.all()
        if wards.exists():
            return wards.filter(unique_id=ticket.ward_id).exists()
    if ticket.panchayat_id:
        panchayats = access_config.panchayats.all()
        if panchayats.exists():
            return panchayats.filter(unique_id=ticket.panchayat_id).exists()
    if ticket.zone_id:
        zones = access_config.zones.all()
        if zones.exists():
            return zones.filter(unique_id=ticket.zone_id).exists()
    return True


def _staff_for_hierarchy_level(project_id, level_num, ticket):
    """Active staff at `level_num` of `project_id`'s staff hierarchy whose
    geo grants cover `ticket` — see `_staff_geo_matches`. None if the level
    isn't configured or nobody at it covers this ticket's geography.
    """
    from app.models.role_assigns.projectStaffHierarchy import ProjectStaffHierarchy
    from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails

    hierarchy_entry = ProjectStaffHierarchy.objects.filter(
        project_id=project_id, level=level_num, is_deleted=False,
    ).first()
    if not hierarchy_entry:
        return None

    candidates = (
        StaffcreationOfficeDetails.objects.filter(
            project_id=project_id,
            staffusertype_id=hierarchy_entry.staffusertype_id_id,
            approval_status=StaffcreationOfficeDetails.APPROVAL_APPROVED,
            is_active=True,
            is_deleted=False,
        )
        .prefetch_related("access_configuration__zones", "access_configuration__panchayats", "access_configuration__wards")
        .order_by("staff_unique_id")
    )
    for staff in candidates:
        if _staff_geo_matches(staff, ticket):
            return staff
    return None


def get_entry_level_staff(ticket):
    """The geo-matching active staff member holding the lowest-numbered
    *enabled* escalation level of `ticket.project_id`'s staff hierarchy, or
    None if the project has no enabled level configured or nobody at that
    level covers this ticket's zone/panchayat/ward.

    Which levels are "enabled" is per-SLA-rule (`ComplaintSlaEscalationLevel.
    is_enabled`) — a project's hierarchy may define Driver/Operator/Supervisor/
    Project Admin/Company Admin, but a given SLA rule can disable the lower
    ones so tickets start at Supervisor instead. Falls back to the project's
    raw level 0 if no SLA rule (and so no escalation_levels) matches yet.
    """
    if not ticket.project_id:
        return None

    entry_level_num = _entry_level_number(ticket)
    if entry_level_num is None:
        return None

    return _staff_for_hierarchy_level(ticket.project_id, entry_level_num, ticket)


def _entry_level_number(ticket):
    """Lowest-numbered enabled `ComplaintSlaEscalationLevel.level` for the
    ticket's best-matching SLA rule, or 0 if no SLA rule/no enabled levels are
    configured yet (falls back to the hierarchy's raw level 0)."""
    sla_rule = _best_sla_rule(ticket)
    if not sla_rule:
        return 0

    lowest_enabled = (
        sla_rule.escalation_levels.filter(is_enabled=True, is_deleted=False)
        .order_by("level")
        .values_list("level", flat=True)
        .first()
    )
    return lowest_enabled if lowest_enabled is not None else 0


def apply_routing_and_sla(ticket, save=True):
    """Fill `assigned_staff` (from the project's lowest enabled hierarchy
    level) and `first_response_due_at` (from the best-matching SLA rule) on
    `ticket` — only touching fields that are currently empty. Returns the
    list of updated field names.
    """
    updated_fields = []
    now = timezone.now()

    if not ticket.assigned_staff_id:
        staff = get_entry_level_staff(ticket)
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
    if not sla_rule:
        routing_rule = _best_routing_rule(ticket)
        if routing_rule and routing_rule.sla_rule_id:
            sla_rule = routing_rule.sla_rule

    if sla_rule:
        add_minutes = _add_business_minutes if sla_rule.working_hours_only else (
            lambda start, minutes: start + timedelta(minutes=minutes)
        )
        if not ticket.first_response_due_at and sla_rule.assign_within_minutes:
            ticket.first_response_due_at = add_minutes(now, sla_rule.assign_within_minutes)
            updated_fields.append("first_response_due_at")

    if ticket.next_escalation_due_at is None:
        from app.services.complaint_escalation import set_initial_escalation_due_date

        set_initial_escalation_due_date(ticket, save=False)
        updated_fields.append("escalation_level")
        updated_fields.append("next_escalation_due_at")

    if save and updated_fields:
        ticket.save(update_fields=updated_fields)

    return updated_fields


def perform_escalation(ticket, reason=None, actor_user=None, by_system=False):
    """Manually escalate `ticket` one hop up its project's staff hierarchy.

    Thin wrapper over `complaint_escalation.escalate_ticket` kept so the
    `/escalate/` API action's import doesn't need to change; the actual
    hierarchy walk/notification logic lives there (shared with the automated
    SLA-breach sweep).
    """
    from app.services.complaint_escalation import escalate_ticket

    return escalate_ticket(ticket, reason=reason, escalated_by=actor_user, by_system=by_system)
