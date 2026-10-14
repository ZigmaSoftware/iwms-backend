from django.core.management.base import BaseCommand

from app.services.stale_trip_closer import close_stale_trips


class Command(BaseCommand):
    help = (
        "Close past-dated In Progress trips as Completed, marking unresolved "
        "stops Missed. Also run nightly by the daily trip scheduler."
    )

    def handle(self, *args, **options):
        result = close_stale_trips()
        self.stdout.write(
            f"Closed {len(result['closed'])} trip(s), "
            f"skipped {len(result['skipped_pending_decision'])} awaiting a "
            f"supervisor decision, {len(result['failed'])} failed; "
            f"{result['stops_marked_missed']} stop(s) marked missed."
        )
