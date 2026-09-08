"""One catch-all routing rule per category (geo-agnostic: state/district/
panchayat/zone/ward all left None here mean "any", so this is the fallback
rule every ticket in that category matches when nothing more specific
exists).

Pins the category's category-wide SLA rule, so `apply_routing_and_sla` has a
fallback `sla_rule` when no subcategory/priority/source-specific SLA rule
matches a ticket more precisely.

Must run AFTER `complaint_ticket_category` and `complaint_sla_rule`.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintCategory, ComplaintSlaRule
from app.models.complaint_management.transactions import ComplaintRoutingRule


class ComplaintRoutingRuleSeeder(BaseSeeder):
    name = "complaint_routing_rule"

    def run(self):
        total = 0
        for category in ComplaintCategory.objects.filter(is_deleted=False):
            sla_rule = ComplaintSlaRule.objects.filter(
                category=category, subcategory__isnull=True, is_deleted=False
            ).first()
            ComplaintRoutingRule.objects.get_or_create(
                category=category,
                subcategory=None,
                state=None,
                district=None,
                panchayat=None,
                zone=None,
                ward=None,
                priority=None,
                defaults={
                    "sla_rule": sla_rule,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint routing rules seeded ({total} records)---")
