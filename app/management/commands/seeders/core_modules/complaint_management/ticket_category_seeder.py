from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintModule,
    ComplaintPriority,
    ComplaintTeam,
)


class ComplaintCategorySeeder(BaseSeeder):
    name = "complaint_ticket_category"

    # (category_code, category_name, default_priority_code, default_team_code,
    #  module_code, requires_location, requires_media, sort_order)
    #
    # `default_team_code` requires the `complaint_team` seed group to have
    # already run — a category seeded before its team exists just gets a
    # null default_team (get_or_create only sets defaults on first insert),
    # and no ComplaintRoutingRule can be generated for it. Run
    # `complaint_team` before `complaint_ticket_category`.
    CATEGORIES = [
        ("MISSED_PICKUP", "Missed Pickup", "P2", "SANITATION", "SANITATION", True, False, 10),
        ("BULK_WASTE", "Bulk Waste Pickup", "P3", "SANITATION", "SANITATION", True, True, 20),
        ("WORKER_CONDUCT", "Worker Conduct", "P2", "SANITATION_L2", "GENERAL", False, False, 30),
        ("VEHICLE_ISSUE", "Vehicle Issue", "P3", "SANITATION", "TRANSPORT", True, True, 40),
        ("BILLING_QUERY", "Billing Inquiry", "P3", "BILLING", "CUSTOMER_SERVICE", False, False, 50),
        ("ADDRESS_CHANGE", "Change of Address", "P3", "ADDRESS_DESK", "CUSTOMER_SERVICE", False, False, 60),
        ("GARBAGE", "Garbage", "P2", "SANITATION", "SANITATION", True, False, 70),
        ("PUBLIC_TOILET", "Public Toilet", "P2", "SANITATION", "SANITATION", True, False, 80),
        ("OTHER", "Other", "P4", "GENERAL", "GENERAL", False, False, 90),
    ]

    def run(self):
        for code, name, priority_code, team_code, module_code, req_loc, req_media, sort_order in self.CATEGORIES:
            priority = ComplaintPriority.objects.filter(priority_code=priority_code).first()
            team = ComplaintTeam.objects.filter(team_code=team_code, is_deleted=False).first()
            module = ComplaintModule.objects.filter(module_code=module_code).first()
            category, created = ComplaintCategory.objects.get_or_create(
                category_code=code,
                defaults={
                    "category_name": name,
                    "default_priority": priority,
                    "default_team": team,
                    "module": module,
                    "requires_location": req_loc,
                    "requires_media": req_media,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            # Backfill default_team on a category that was seeded before this
            # column existed / before the team seed group had run — never
            # overwrites an operator's manual choice.
            if not created and not category.default_team_id and team:
                category.default_team = team
                category.save(update_fields=["default_team"])
        self.log(f"---Complaint ticket categories seeded ({len(self.CATEGORIES)} records)---")
