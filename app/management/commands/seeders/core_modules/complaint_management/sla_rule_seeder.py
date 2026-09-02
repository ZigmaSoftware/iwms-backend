"""SLA rules per sub-category, with a category-wide fallback.

Originally one rule per category with `subcategory=None`, which the SLA list
rendered as "All". Now each sub-category gets its own rule keyed off the
priority that actually applies to it — a sub-category's `default_priority`
where one is set, otherwise the parent category's — so a "Dead animal" (P1)
under Garbage gets a 4-hour resolve target rather than inheriting the
category's P2 24-hour one.

The per-category rule (`subcategory=None`) is deliberately KEPT alongside
them. A ticket may be raised against a category with no sub-category chosen
(the public form makes sub-type optional), and `_best_sla_rule` only ever
considers rules whose sub-category is null or matches — with no
category-wide row such a ticket would resolve no SLA at all and get no due
dates. Since `_sla_specificity` ranks a sub-category match above a bare
category match, the specific rule still wins whenever a sub-category is set.

Must run AFTER `complaint_ticket_category` and `complaint_ticket_subcategory`
(needs both, plus each category's `default_priority`/`default_team`) and
BEFORE `complaint_routing_rule` (which looks up the rules created here).
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintSlaRule,
    ComplaintSubcategory,
)


class ComplaintSlaRuleSeeder(BaseSeeder):
    name = "complaint_sla_rule"

    # priority_code -> (assign_within_minutes, resolve_within_minutes,
    #                   escalation_after_minutes)
    PRIORITY_SLA_MINUTES = {
        "P1": (15, 240, 60),
        "P2": (60, 1440, 360),
        "P3": (120, 4320, 1440),
        "P4": (240, 10080, None),
    }

    # Used when a priority code is not in the table above.
    DEFAULT_SLA_MINUTES = (120, 4320, 1440)

    def _upsert(self, *, category, subcategory, priority):
        """Create the rule for this (category, subcategory, priority) if absent.

        Returns True when a row was created, so the caller can report real
        work separately from an idempotent re-run.
        """
        assign_within, resolve_within, escalate_after = self.PRIORITY_SLA_MINUTES.get(
            priority.priority_code, self.DEFAULT_SLA_MINUTES
        )
        _, created = ComplaintSlaRule.objects.get_or_create(
            category=category,
            subcategory=subcategory,
            priority=priority,
            source=None,
            defaults={
                "assign_within_minutes": assign_within,
                "resolve_within_minutes": resolve_within,
                "escalation_after_minutes": escalate_after,
                # `escalation_team` is deliberately left unset. Escalation
                # targets come from `ComplaintTeam.escalates_to` — see
                # `perform_escalation` — so a value here would look like
                # configuration while changing nothing.
                "is_active": True,
                "is_deleted": False,
            },
        )
        return created

    def run(self):
        subcategory_rules = 0
        fallback_rules = 0
        skipped = []

        for category in ComplaintCategory.objects.filter(
            is_deleted=False
        ).select_related("default_priority", "default_team"):
            category_priority = category.default_priority
            if not category_priority:
                skipped.append(category.category_code)
                continue

            # Category-wide fallback, for tickets raised without a sub-category.
            self._upsert(category=category, subcategory=None, priority=category_priority)
            fallback_rules += 1

            # One rule per sub-category, at the priority that applies to it.
            for subcategory in ComplaintSubcategory.objects.filter(
                category=category, is_deleted=False
            ).select_related("default_priority"):
                self._upsert(
                    category=category,
                    subcategory=subcategory,
                    priority=subcategory.default_priority or category_priority,
                )
                subcategory_rules += 1

        if skipped:
            self.log(
                "---Complaint SLA rules: skipped "
                f"{', '.join(skipped)} (no default priority on the category)---"
            )
        self.log(
            f"---Complaint SLA rules seeded ({subcategory_rules} sub-category "
            f"+ {fallback_rules} category-wide = "
            f"{subcategory_rules + fallback_rules} records)---"
        )
