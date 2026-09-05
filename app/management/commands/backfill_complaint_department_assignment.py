"""One-time fix for tickets created before `ComplaintTicketViewSet.perform_create`
called `apply_routing_and_sla` — that viewset only wrote the ticket and its
initial status history, so tickets created via the staff/admin "New Ticket"
screen never got a `department`/`assigned_staff`, unlike the citizen and
public-grievance intake paths which always called routing.

Run once after deploying that fix to catch up any tickets stuck without a
department/assignee. Safe to run repeatedly — `apply_routing_and_sla` only
fills fields that are still empty.
"""

from django.core.management.base import BaseCommand

from app.models.complaint_management import ComplaintTicket
from app.services.complaint_ticket_routing import apply_routing_and_sla


class Command(BaseCommand):
    help = "Assign a department/staff to any complaint ticket missing one."

    def handle(self, *args, **options):
        stuck = ComplaintTicket.objects.filter(
            department__isnull=True, is_deleted=False,
        ).select_related("category")

        updated = 0
        skipped = 0
        for ticket in stuck:
            fields = apply_routing_and_sla(ticket, save=True)
            if "department" in fields:
                updated += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled department/assignment on {updated} ticket(s); "
                f"{skipped} had no matching routing rule or category default_department."
            )
        )
