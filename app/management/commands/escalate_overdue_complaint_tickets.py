"""Sweep complaint tickets past their current escalation deadline and bump
each one to the next level of its project's staff hierarchy.

This project has no Celery/beat worker; periodic jobs run as management
commands on an OS-level cron. Schedule this one every 15 minutes, e.g.:

    */15 * * * * cd /path/to/iwms-backend && python manage.py escalate_overdue_complaint_tickets
"""

from django.core.management.base import BaseCommand

from app.services.complaint_escalation import check_and_escalate_overdue_tickets


class Command(BaseCommand):
    help = "Auto-escalate complaint tickets past their next_escalation_due_at."

    def handle(self, *args, **options):
        count = check_and_escalate_overdue_tickets()
        self.stdout.write(self.style.SUCCESS(f"Escalated {count} ticket(s)."))
