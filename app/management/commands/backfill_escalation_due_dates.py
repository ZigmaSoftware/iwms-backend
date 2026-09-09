"""One-time fix for tickets created before the hierarchy-escalation feature
existed — they never got an `escalation_level`/`next_escalation_due_at`.

Run once after deploying the `0xxx_complaint_escalation_levels` migration.
Safe to run repeatedly: `apply_routing_and_sla` only sets
`next_escalation_due_at` when it is still null.
"""

from django.core.management.base import BaseCommand

from app.models.complaint_management import ComplaintTicket
from app.services.complaint_ticket_routing import apply_routing_and_sla


class Command(BaseCommand):
    help = "Set escalation_level/next_escalation_due_at on open tickets missing it."

    def handle(self, *args, **options):
        stuck = (
            ComplaintTicket.objects.filter(
                next_escalation_due_at__isnull=True,
                is_deleted=False,
            )
            .exclude(status__is_final=True)
            .select_related("category", "priority", "status")
        )

        updated = 0
        skipped = 0
        for ticket in stuck:
            fields = apply_routing_and_sla(ticket, save=True)
            if "next_escalation_due_at" in fields:
                updated += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled next_escalation_due_at on {updated} ticket(s); "
                f"{skipped} had no matching SLA rule/level-0 window."
            )
        )
