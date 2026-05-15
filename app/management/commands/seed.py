from django.conf import settings
from django.core.management.base import BaseCommand

from app.management.commands.seeders.audits.bin_load_log import BinLoadLogSeeder
from app.management.commands.seeders.audits.trip_exception_log import TripExceptionLogSeeder
from app.management.commands.seeders.audits.vehicle_trip_audit import VehicleTripAuditSeeder
from app.management.commands.seeders.assets.bins import BinSeeder
from app.management.commands.seeders.assets.collection_point import CollectionPointSeeder
from app.management.commands.seeders.assets.point_collection import PointCollectionSeeder
# from app.management.commands.seeders.assets.weighbridge import WeighbridgeCheckSeeder
from app.management.commands.seeders.collections import COLLECTION_SEEDERS
from app.management.commands.seeders.common_masters import COMMON_MASTER_SEEDERS
from app.management.commands.seeders.customers import CUSTOMER_SEEDERS
from app.management.commands.seeders.grivences import GRIEVANCE_SEEDERS
from app.management.commands.seeders.masters import MASTER_SEEDERS as CORE_MASTER_SEEDERS
from app.management.commands.seeders.process.routeplan_seeder import RoutePlanSeeder
from app.management.commands.seeders.process.zone_property_load_tracker import (
    ZonePropertyLoadTrackerSeeder,
)
from app.management.commands.seeders.role_assigns import ROLE_ASSIGN_SEEDERS
from app.management.commands.seeders.screen_managements import PERMISSION_SEEDERS
from app.management.commands.seeders.superadmin_masters import (
    COMPANY_SEEDERS,
    PLATFORM_SEEDERS,
)
from app.management.commands.seeders.transport_masters.fuel import FuelSeeder
from app.management.commands.seeders.transport_masters.trip import TripSeeder
from app.management.commands.seeders.transport_masters.trip_attendance import (
    TripAttendanceSeeder,
)
from app.management.commands.seeders.transport_masters.trip_definition import (
    TripDefinitionSeeder,
)
from app.management.commands.seeders.transport_masters.trip_instance import (
    TripInstanceSeeder,
)
from app.management.commands.seeders.transport_masters.vehicleCreation import (
    VehicleCreationSeeder,
)
from app.management.commands.seeders.transport_masters.vehicleTypeCreation import (
    VehicleTypeCreationSeeder,
)
from app.management.commands.seeders.user_creations.alternative_staff_template_seeder import (
    AlternativeStaffTemplateSeeder,
)
from app.management.commands.seeders.user_creations.auth_user_seeder import (
    AuthUserSeeder,
)
from app.management.commands.seeders.user_creations.staff_office import StaffOfficeSeeder
from app.management.commands.seeders.user_creations.staff_personal import (
    StaffPersonalSeeder,
)
from app.management.commands.seeders.user_creations.staff_template_seeder import (
    StaffTemplateSeeder,
)
from app.management.commands.seeders.user_creations.supervisor_zone_map import (
    SupervisorZoneMapSeeder,
)
from app.management.commands.seeders.user_creations.unassigned_staff_pool import (
    UnassignedStaffPoolSeeder,
)
from app.management.commands.seeders.waste_types.properties import PropertySeeder
from app.management.commands.seeders.waste_types.subproperties import SubPropertySeeder
from app.management.commands.seeders.waste_types.wastetype import WasteTypeSeeder

# Legacy group definitions, now sourced from model-aligned seeder packages.
MASTER_SEEDERS = [
    *COMMON_MASTER_SEEDERS,
    *CORE_MASTER_SEEDERS,
    WasteTypeSeeder,
    CollectionPointSeeder,
    BinSeeder,
    TripSeeder,
    PointCollectionSeeder,
    # WeighbridgeCheckSeeder,
]

ASSET_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
    FuelSeeder,
]

USER_CREATION_SEEDERS = [
    StaffOfficeSeeder,
    StaffPersonalSeeder,
    SupervisorZoneMapSeeder,
]

VEHICLE_SEEDERS = [
    VehicleTypeCreationSeeder,
    VehicleCreationSeeder,
    ZonePropertyLoadTrackerSeeder,
    RoutePlanSeeder,
    BinLoadLogSeeder,
]

STAFF_SEEDERS = [
    AuthUserSeeder,
    StaffTemplateSeeder,
    TripDefinitionSeeder,
    TripInstanceSeeder,
    TripAttendanceSeeder,
    VehicleTripAuditSeeder,
    TripExceptionLogSeeder,
    UnassignedStaffPoolSeeder,
    AlternativeStaffTemplateSeeder,
]

# --------------------------------------------------
# ORDER MATTERS - DEFINE IT ONCE
# --------------------------------------------------
ORDERED_GROUPS = [
    "platform",
    "masters",
    "assets",
    "collections",
    "role-assigns",
    "company",
    "staff",
    "screen-managements",
    "user-creation",
    "customers",
    "vehicles",
    "grievance",
]

SEED_GROUPS = {
    "platform": PLATFORM_SEEDERS,
    "masters": MASTER_SEEDERS,
    "assets": ASSET_SEEDERS,
    "collections": COLLECTION_SEEDERS,
    "company": COMPANY_SEEDERS,
    # "role-assign": ROLE_ASSIGN_SEEDERS,
    "role-assigns": ROLE_ASSIGN_SEEDERS,
    # "permission": PERMISSION_SEEDERS,
    "screen-managements": PERMISSION_SEEDERS,
    "customers": CUSTOMER_SEEDERS,
    "user-creation": USER_CREATION_SEEDERS,
    "user-creations": USER_CREATION_SEEDERS,
    "grievance": GRIEVANCE_SEEDERS,
    "staff": STAFF_SEEDERS,
    "vehicles": VEHICLE_SEEDERS,

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
                "platform | masters | assets | collections | role-assign | permission | company | "
                "customers | user-creation | vehicles | grievance | staff | all"
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
            # No --group -> run ALL in order
            seeders = SEED_GROUPS["all"]

        # --------------------------------------------------
        # EXECUTE SEEDERS
        # --------------------------------------------------
        self.stdout.write(self.style.WARNING("Starting database seeding...\n"))

        for seeder_cls in seeders:
            seeder = seeder_cls()
            self.stdout.write(self.style.NOTICE(f"Running {seeder_cls.__name__}"))
            seeder.run()

        self.stdout.write(self.style.SUCCESS("\nSeeding completed successfully."))
