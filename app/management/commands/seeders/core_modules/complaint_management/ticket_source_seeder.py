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
        # Also get_or_create'd lazily by PublicGrievanceViewSet.create on
        # first submission — seeded here too so `ComplaintTicketViewSet
        # .counts`'s "public" bucket exists (and reads as a real 0, not
        # "not configured yet") even before anyone has submitted one.
        ("PUBLIC_GRIEVANCE", "Public Grievance"),
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
