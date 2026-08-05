from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintSource


class ComplaintSourceSeeder(BaseSeeder):
    name = "complaint_ticket_source"

    SOURCES = [
        ("MOBILE_APP", "Mobile App"),
        ("WEB", "Web Portal"),
        ("CALL_CENTER", "Call Center"),
        ("ADMIN", "Admin"),
        ("WHATSAPP", "WhatsApp"),
    ]

    def run(self):
        for code, name in self.SOURCES:
            ComplaintSource.objects.get_or_create(
                source_code=code,
                defaults={
                    "source_name": name,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint ticket sources seeded ({len(self.SOURCES)} records)---")
