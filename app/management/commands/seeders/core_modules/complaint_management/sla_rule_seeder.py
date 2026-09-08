"""SLA rules per sub-category, with a category-wide fallback.

One rule per sub-category, keyed off the priority that actually applies to
it — a sub-category's `default_priority` where one is set, otherwise the
parent category's — so a "Dead animal" (P1) under Garbage gets its own
resolve target rather than inheriting the category's slower one. A
category-wide rule (`subcategory=None`) is kept alongside them for tickets
raised without a sub-category chosen (the public form makes sub-type
optional) — `_best_sla_rule` only ever considers rules whose sub-category is
null or matches, so without this fallback such a ticket would resolve no SLA
rule at all. `_sla_specificity` ranks a sub-category match above a bare
category match, so the specific rule still wins whenever a sub-category is set.

`assign_within_minutes` (how long a ticket may sit unassigned before the
first-response SLA is breached) still lives directly on `ComplaintSlaRule`.
Resolution time no longer does — since ComplaintTicket.escalation_level (the
current hierarchy hop) has its own window, seeded here as
`ComplaintSlaEscalationLevel` rows. Those rows only make sense against a real
`ProjectStaffHierarchy`, so they are seeded only for the one project this
dev environment actually has a hierarchy for ("Blue Planet Integrated Waste
Management") — skipped everywhere else.

Must run AFTER `complaint_ticket_category`, `complaint_ticket_subcategory`
and `project_staff_hierarchy` (needs the category tree, each category's
`default_priority`, and — for the escalation-level step — Blue Planet's
hierarchy) and BEFORE `complaint_routing_rule` (which looks up the rules
created here).
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintSlaEscalationLevel,
    ComplaintSlaRule,
    ComplaintSubcategory,
)
from app.models.role_assigns.projectStaffHierarchy import ProjectStaffHierarchy
from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
from app.models.superadmin_masters.project import Project


class ComplaintSlaRuleSeeder(BaseSeeder):
    name = "complaint_sla_rule"

    # The only project this dev environment has a real ProjectStaffHierarchy
    # for. Escalation levels are meaningless without one, so they're seeded
    # only here — every other project's SLA rules are created with no levels,
    # same as before this feature existed, until someone configures a
    # hierarchy for them and adds levels through the SLA Rule screen.
    HIERARCHY_PROJECT_NAME = "Blue Planet Integrated Waste Management"

    # priority_code -> assign_within_minutes (first-response SLA only —
    # resolution time comes from ComplaintSlaEscalationLevel now).
    PRIORITY_ASSIGN_MINUTES = {
        "P1": 15,
        "P2": 60,
        "P3": 120,
        "P4": 240,
    }
    DEFAULT_ASSIGN_MINUTES = 120

    # Resolve-within-minutes per hierarchy level, keyed by priority code.
    # Only levels with a matching active staff member in
    # HIERARCHY_PROJECT_NAME are actually seeded (see `_levels_for_project`) —
    # Level 1 (Company Admin) has no staff yet in this dev environment, so it
    # is skipped everywhere below regardless of what's listed here.
    LEVEL_MINUTES_BY_PRIORITY = {
        "P1": {2: 30, 3: 15, 4: 10, 5: 10},
        "P2": {2: 60, 3: 30, 4: 20, 5: 20},
        "P3": {2: 240, 3: 120, 4: 60, 5: 60},
        "P4": {2: 480, 3: 240, 4: 120, 5: 120},
    }
    DEFAULT_LEVEL_MINUTES = {2: 240, 3: 120, 4: 60, 5: 60}

    # Escalation starts at Supervisor for this deployment — Company Admin
    # (1) and Project Admin (2) are never the entry point even when staffed,
    # they're only reached by escalating up from Supervisor.
    NON_ENTRY_LEVELS = {1, 2}

    def _levels_for_project(self, project):
        """Hierarchy levels that actually have an active staff member in
        `project`, excluding `NON_ENTRY_LEVELS` — seeding a level nobody
        occupies would leave tickets that land on it permanently
        unassigned, and Company/Project Admin should only be reached by
        escalating up, never as the entry point."""
        if not project:
            return []
        occupied_levels = set(
            ProjectStaffHierarchy.objects.filter(
                project_id=project, is_deleted=False,
            )
            .filter(
                staffusertype_id__in=StaffcreationOfficeDetails.objects.filter(
                    project_id=project,
                    approval_status=StaffcreationOfficeDetails.APPROVAL_APPROVED,
                    is_active=True,
                    is_deleted=False,
                ).values("staffusertype_id")
            )
            .values_list("level", flat=True)
        )
        return sorted(occupied_levels - self.NON_ENTRY_LEVELS)

    def _upsert(self, *, category, subcategory, priority, hierarchy_levels):
        assign_within = self.PRIORITY_ASSIGN_MINUTES.get(
            priority.priority_code, self.DEFAULT_ASSIGN_MINUTES
        )
        rule, created = ComplaintSlaRule.objects.get_or_create(
            category=category,
            subcategory=subcategory,
            priority=priority,
            source=None,
            defaults={
                "assign_within_minutes": assign_within,
                "is_active": True,
                "is_deleted": False,
            },
        )
        if not created:
            return rule, False

        level_minutes = self.LEVEL_MINUTES_BY_PRIORITY.get(
            priority.priority_code, self.DEFAULT_LEVEL_MINUTES
        )
        for level in hierarchy_levels:
            minutes = level_minutes.get(level)
            if minutes is None:
                continue
            ComplaintSlaEscalationLevel.objects.get_or_create(
                sla_rule=rule,
                level=level,
                defaults={
                    "is_enabled": True,
                    "resolve_within_minutes": minutes,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        return rule, True

    def run(self):
        hierarchy_project = Project.objects.filter(
            name=self.HIERARCHY_PROJECT_NAME, is_deleted=False,
        ).first()
        hierarchy_levels = self._levels_for_project(hierarchy_project)
        if hierarchy_project and not hierarchy_levels:
            self.log(
                f"---Complaint SLA rules: '{self.HIERARCHY_PROJECT_NAME}' has no "
                "occupied hierarchy levels yet — seeding rules with no escalation levels---"
            )

        subcategory_rules = 0
        fallback_rules = 0
        skipped = []

        for category in ComplaintCategory.objects.filter(
            is_deleted=False
        ).select_related("default_priority"):
            category_priority = category.default_priority
            if not category_priority:
                skipped.append(category.category_code)
                continue

            # Category-wide fallback, for tickets raised without a sub-category.
            _, created = self._upsert(
                category=category, subcategory=None, priority=category_priority,
                hierarchy_levels=hierarchy_levels,
            )
            fallback_rules += 1 if created else 0

            # One rule per sub-category, at the priority that applies to it.
            for subcategory in ComplaintSubcategory.objects.filter(
                category=category, is_deleted=False
            ).select_related("default_priority"):
                _, created = self._upsert(
                    category=category,
                    subcategory=subcategory,
                    priority=subcategory.default_priority or category_priority,
                    hierarchy_levels=hierarchy_levels,
                )
                subcategory_rules += 1 if created else 0

        if skipped:
            self.log(
                "---Complaint SLA rules: skipped "
                f"{', '.join(skipped)} (no default priority on the category)---"
            )
        self.log(
            f"---Complaint SLA rules seeded ({subcategory_rules} sub-category "
            f"+ {fallback_rules} category-wide = "
            f"{subcategory_rules + fallback_rules} new records; "
            f"escalation levels seeded per rule: {hierarchy_levels or 'none'})---"
        )
