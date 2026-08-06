from django.core.management.base import BaseCommand

from app.management.commands.seeders.masters.customer_masters.customerCreation import (
    backfill_missing_customer_ids,
)
from app.management.commands.seeders.superadmin.staff_management.staff_office import (
    backfill_missing_staff_ids,
)


class Command(BaseCommand):
    help = "Backfill missing CUST and STF display IDs across every company/project"

    def handle(self, *args, **options):
        customer_count = backfill_missing_customer_ids()
        staff_count = backfill_missing_staff_ids()
        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {customer_count} customer IDs and {staff_count} staff IDs."
            )
        )
