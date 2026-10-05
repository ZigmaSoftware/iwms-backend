from django.core.management.base import BaseCommand
from django.db import transaction

from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin.screen_management.userscreen import UserScreen

SCREEN = "static-route-audit"
# Companies that can open another audit get the new one too: the first of
# these that exists is copied (older databases have no permission-audit).
TEMPLATE_SCREENS = ("permission-audit", "common-audit")


class Command(BaseCommand):
    screen_name = SCREEN
    help = (
        "Register the Static Route Audit screen on an existing database without "
        "re-running the whole permission seeder (which also re-seeds access "
        "configurations). Idempotent. Fresh installs get it from the seeder."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        SCREEN = self.screen_name
        template = next(
            (
                screen
                for name in TEMPLATE_SCREENS
                if (screen := UserScreen.objects.filter(userscreen_name=name, is_deleted=False).first())
            ),
            None,
        )
        if not template:
            self.stderr.write("No audit screen found to copy from; run the permission seeder instead.")
            return

        screen = UserScreen.objects.filter(userscreen_name=SCREEN).first()
        if screen is None:
            last = (
                UserScreen.objects.filter(mainscreen_id=template.mainscreen_id)
                .order_by("-order_no")
                .values_list("order_no", flat=True)
                .first()
            )
            screen = UserScreen.objects.create(
                userscreen_name=SCREEN,
                mainscreen_id=template.mainscreen_id,
                folder_name=SCREEN,
                icon_name=SCREEN,
                order_no=(last or 0) + 1,
                is_active=True,
                is_deleted=False,
            )
            self.stdout.write(f"Created screen '{SCREEN}' ({screen.unique_id}).")
        else:
            self.stdout.write(f"Screen '{SCREEN}' already exists ({screen.unique_id}).")

        granted = 0
        for grant in CompanyUserScreenPermission.objects.filter(
            userscreen_id=template.unique_id, is_deleted=False,
        ):
            _, created = CompanyUserScreenPermission.objects.get_or_create(
                company_id=grant.company_id,
                project_id=grant.project_id,
                mainscreen_id=screen.mainscreen_id,
                userscreen_id=screen.unique_id,
                userscreenaction_id=grant.userscreenaction_id,
                defaults={
                    "order_no": grant.order_no,
                    "description": f"{SCREEN} (copied from {template.userscreen_name})",
                    "is_active": grant.is_active,
                    "is_deleted": False,
                },
            )
            granted += int(created)
        self.stdout.write(f"Company grants added: {granted} (copied from '{template.userscreen_name}').")
