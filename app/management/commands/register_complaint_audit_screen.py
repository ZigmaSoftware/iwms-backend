from app.management.commands.register_static_route_audit_screen import (
    Command as RegisterAuditScreenCommand,
)


class Command(RegisterAuditScreenCommand):
    screen_name = "complaint-audit"
    help = (
        "Register the Complaint Audit screen on an existing database without "
        "re-running the whole permission seeder (which also re-seeds access "
        "configurations). Idempotent. Fresh installs get it from the seeder."
    )
