from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintModule


class ComplaintModuleSeeder(BaseSeeder):
    name = "complaint_ticket_module"

    # (module_code, module_name, sort_order)
    MODULES = [
        ("GENERAL", "General / Other", 0),
        ("SANITATION", "Sanitation & Collection", 10),
        ("TRANSPORT", "Transport & Vehicles", 20),
        ("CUSTOMER_SERVICE", "Customer Service", 30),
    ]

    def run(self):
        for code, name, sort_order in self.MODULES:
            ComplaintModule.objects.get_or_create(
                module_code=code,
                defaults={
                    "module_name": name,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint ticket modules seeded ({len(self.MODULES)} records)---")
