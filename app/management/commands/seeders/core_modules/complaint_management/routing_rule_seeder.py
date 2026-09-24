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
                category_id=category.unique_id, subcategory_id__isnull=True, is_deleted=False
            ).first()
            ComplaintRoutingRule.objects.get_or_create(
                category_id=category.unique_id,
                subcategory_id=None,
                state_id=None,
                district_id=None,
                panchayat_id=None,
                zone_id=None,
                ward_id=None,
                priority_id=None,
                defaults={
                    "sla_rule_id": sla_rule.unique_id if sla_rule else None,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint routing rules seeded ({total} records)---")
