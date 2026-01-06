from django.conf import settings
from django.core.management.base import BaseCommand

from api.management.commands.seeders.complaints import GRIEVANCE_SEEDERS
from api.management.commands.seeders.masters import MASTER_SEEDERS
from api.management.commands.seeders.assets import ASSET_SEEDERS
from api.management.commands.seeders.role_assign import ROLE_ASSIGN_SEEDERS
from api.management.commands.seeders.permissions import PERMISSION_SEEDERS
from api.management.commands.seeders.customers import CUSTOMER_SEEDERS
from api.management.commands.seeders.userCreation import USER_CREATION_SEEDERS
from api.management.commands.seeders.vehicles import VEHICLE_SEEDERS


# --------------------------------------------------
# ORDER MATTERS – DEFINE IT ONCE
# --------------------------------------------------
ORDERED_GROUPS = [
    "masters",
    "assets",
    "role-assign",
    "permission",
    "customers",
    "user-creation",
    "vehicles",
    "grievance"
]

SEED_GROUPS = {
    "masters": MASTER_SEEDERS,
    "assets": ASSET_SEEDERS,
    "role-assign": ROLE_ASSIGN_SEEDERS,
    "permission": PERMISSION_SEEDERS,
    "customers": CUSTOMER_SEEDERS,
    "user-creation": USER_CREATION_SEEDERS,
    "grievance": GRIEVANCE_SEEDERS,
    "vehicles": VEHICLE_SEEDERS
}

# --------------------------------------------------
# EXPLICIT "ALL" GROUP (NO DUPLICATES)
# --------------------------------------------------
SEED_GROUPS["all"] = [
    seeder
    for group in ORDERED_GROUPS
    for seeder in SEED_GROUPS[group]
]


class Command(BaseCommand):
    help = "Run database seeders"

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            type=str,
            help=(
                "Seeder group: "
                "masters | assets | role-assign | permission | customers | user-creation | vehicles | all"
            ),
        )

    def handle(self, *args, **options):

        # --------------------------------------------------
        # SAFETY CHECKS
        # --------------------------------------------------
        if settings.ENVIRONMENT == "production":
            self.stdout.write(
                self.style.ERROR("Seeding is disabled in PRODUCTION environment")
            )
            return

        if not settings.DEBUG:
            self.stdout.write(
                self.style.ERROR("Seeding blocked because DEBUG=False")
            )
            return

        # --------------------------------------------------
        # RESOLVE GROUP
        # --------------------------------------------------
        group = options.get("group")

        if group:
            seeders = SEED_GROUPS.get(group)
            if not seeders:
                self.stdout.write(
                    self.style.ERROR(
                        f"Invalid group '{group}'. Use one of: {', '.join(SEED_GROUPS.keys())}"
                    )
                )
                return
        else:
            # No --group → run ALL in order
            seeders = SEED_GROUPS["all"]

        # --------------------------------------------------
        # EXECUTE SEEDERS
        # --------------------------------------------------
        self.stdout.write(self.style.WARNING(" Starting database seeding...\n"))

        for seeder_cls in seeders:
            seeder = seeder_cls()
            self.stdout.write(self.style.NOTICE(f"➡ Running {seeder_cls.__name__}"))
            seeder.run()

        self.stdout.write(self.style.SUCCESS("\n Seeding completed successfully"))
