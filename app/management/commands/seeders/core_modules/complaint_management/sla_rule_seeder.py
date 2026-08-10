"""One default SLA rule per category — ported from the government backend's
sla_rule_seeder.py unchanged (geo-agnostic; no adaptation needed).

Must run AFTER `complaint_ticket_category` (needs each category's
`default_priority` and `default_team`) and BEFORE `complaint_routing_rule`
(which looks up the SLA rule this seeder creates).
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintCategory, ComplaintSlaRule


class ComplaintSlaRuleSeeder(BaseSeeder):
    name = "complaint_sla_rule"

    # One default SLA rule per category, keyed off the category's own default
    # priority. (assign_within_minutes, resolve_within_minutes, escalation_after_minutes)
    PRIORITY_SLA_MINUTES = {
        "P1": (15, 240, 60),
        "P2": (60, 1440, 360),
        "P3": (120, 4320, 1440),
        "P4": (240, 10080, None),
    }

    def run(self):
        total = 0
        for category in ComplaintCategory.objects.filter(is_deleted=False):
            priority = category.default_priority
            if not priority:
                self.log(f"Category '{category.category_code}' has no default priority - skipping SLA rule.")
                continue
            assign_within, resolve_within, escalate_after = self.PRIORITY_SLA_MINUTES.get(
                priority.priority_code, (120, 4320, 1440)
            )
            ComplaintSlaRule.objects.get_or_create(
                category=category,
                subcategory=None,
                priority=priority,
                source=None,
                defaults={
                    "assign_within_minutes": assign_within,
                    "resolve_within_minutes": resolve_within,
                    "escalation_after_minutes": escalate_after,
                    "escalation_team": category.default_team.escalates_to if category.default_team else None,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint SLA rules seeded ({total} records)---")
