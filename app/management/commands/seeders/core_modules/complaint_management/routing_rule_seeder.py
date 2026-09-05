"""One catch-all routing rule per category (geo-agnostic: state/district/
panchayat/zone/ward all left None here mean "any", so this is the fallback
rule every ticket in that category matches when nothing more specific
exists).

Routes by the category's `default_department`. Categories seeded before
`department_roster_seeder` has run (or run again to backfill) have no
default_department yet and are skipped — re-run this seeder after the
roster seeder to pick them up.

Must run AFTER `complaint_ticket_category`, `complaint_sla_rule`, and
`department_roster_seeder` (needs `default_department`).
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintCategory, ComplaintSlaRule
from app.models.complaint_management.transactions import ComplaintRoutingRule


class ComplaintRoutingRuleSeeder(BaseSeeder):
    name = "complaint_routing_rule"

    def run(self):
        total = 0
        for category in ComplaintCategory.objects.filter(is_deleted=False):
            if not category.default_department_id:
                self.log(f"Category '{category.category_code}' has no default department - skipping routing rule.")
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
                    "department": category.default_department,
                    "sla_rule": sla_rule,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint routing rules seeded ({total} records)---")
