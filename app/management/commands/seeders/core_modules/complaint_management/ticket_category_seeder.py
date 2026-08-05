from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintCategory, ComplaintModule, ComplaintPriority


class ComplaintCategorySeeder(BaseSeeder):
    name = "complaint_ticket_category"

    # (category_code, category_name, default_priority_code, module_code,
    #  requires_location, requires_media, sort_order)
    CATEGORIES = [
        ("MISSED_PICKUP", "Missed Pickup", "P2", "SANITATION", True, False, 10),
        ("BULK_WASTE", "Bulk Waste Pickup", "P3", "SANITATION", True, True, 20),
        ("WORKER_CONDUCT", "Worker Conduct", "P2", "GENERAL", False, False, 30),
        ("VEHICLE_ISSUE", "Vehicle Issue", "P3", "TRANSPORT", True, True, 40),
        ("BILLING_QUERY", "Billing Inquiry", "P3", "CUSTOMER_SERVICE", False, False, 50),
        ("ADDRESS_CHANGE", "Change of Address", "P3", "CUSTOMER_SERVICE", False, False, 60),
        ("GARBAGE", "Garbage", "P2", "SANITATION", True, False, 70),
        ("PUBLIC_TOILET", "Public Toilet", "P2", "SANITATION", True, False, 80),
        ("OTHER", "Other", "P4", "GENERAL", False, False, 90),
    ]

    def run(self):
        for code, name, priority_code, module_code, req_loc, req_media, sort_order in self.CATEGORIES:
            priority = ComplaintPriority.objects.filter(priority_code=priority_code).first()
            module = ComplaintModule.objects.filter(module_code=module_code).first()
            ComplaintCategory.objects.get_or_create(
                category_code=code,
                defaults={
                    "category_name": name,
                    "default_priority": priority,
                    "module": module,
                    "requires_location": req_loc,
                    "requires_media": req_media,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint ticket categories seeded ({len(self.CATEGORIES)} records)---")
