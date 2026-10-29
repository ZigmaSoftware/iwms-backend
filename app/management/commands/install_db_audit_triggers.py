from django.core.management.base import BaseCommand

from app.services.db_change_audit import drop_triggers, install_triggers, is_enabled


class Command(BaseCommand):
    help = (
        "Rebuild the DB Change Audit triggers that record INSERT/UPDATE/DELETE "
        "made on the database directly (outside the app). migrate already does "
        "this; run it by hand after changing tables outside of migrations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--drop", action="store_true",
            help="Only drop the triggers (stops recording direct DB changes).",
        )

    def handle(self, *args, **options):
        if options["drop"]:
            self.stdout.write(f"Dropped {drop_triggers()} trigger(s).")
            return
        if not is_enabled():
            self.stderr.write(
                "DB change audit is off: needs MySQL/MariaDB and DB_CHANGE_AUDIT_ENABLED not set to false."
            )
            return
        self.stdout.write(f"Installed DB change audit triggers on {install_triggers()} table(s).")
