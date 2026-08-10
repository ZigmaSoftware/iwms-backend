"""One catch-all routing rule per category — ported from the government
backend's routing_rule_seeder.py unchanged (geo-agnostic: state/district/
panchayat/zone/ward all left None here mean "any", so this is the fallback
rule every ticket in that category matches when nothing more specific
exists).

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
            if not category.default_team:
                self.log(f"Category '{category.category_code}' has no default team - skipping routing rule.")
                continue
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
                    "team": category.default_team,
                    "sla_rule": sla_rule,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint routing rules seeded ({total} records)---")
