"""Close web login sessions whose browser never reported the logout.

A tab closed (or a machine put to sleep) mid-session never calls the logout
API, so its LoginAudit row would stay open forever. This stamps those rows
with the idle-timeout / token-expiry logout time and used hours.

Suggested cron (every 10 minutes):
    */10 * * * * cd /path/to/iwms-backend && python manage.py close_idle_login_sessions
"""

from django.core.management.base import BaseCommand

from app.services.login_session import close_stale_sessions


class Command(BaseCommand):
    help = "Stamp logout time on idle / expired web login sessions."

    def handle(self, *args, **options):
        closed = close_stale_sessions()
        self.stdout.write(self.style.SUCCESS(f"Closed {closed} stale login session(s)."))
