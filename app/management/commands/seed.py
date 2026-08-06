from django.conf import settings
from django.core.management.base import BaseCommand

# ============================================================
# IMPORTS — organized by URL group they belong to
# ============================================================

# superadmin (router: superadmin/company, superadmin/project)
from app.management.commands.seeders.superadmin_masters import (
    BluePlanetSeeder,
    COMPANY_SEEDERS,
    PLATFORM_SEEDERS,
)

# common-masters (router: common-masters/continents, countries, states)
from app.management.commands.seeders.superadmin.common_masters import COMMON_MASTER_SEEDERS as _COMMON_MASTER_SEEDERS

# masters (router: masters/districts, cities, zones, wards, panchayat, ...)
from app.management.commands.seeders.masters import MASTER_SEEDERS as CORE_MASTER_SEEDERS
from app.management.commands.seeders.masters.department import DepartmentSeeder
from app.management.commands.seeders.masters.designation import DesignationSeeder

# waste-types (router: waste-types/properties, subproperties, wastetypes, bins —
# wastetypes/bins merged in from the legacy "assets" group)
from app.management.commands.seeders.masters.waste_masters.properties import PropertySeeder
from app.management.commands.seeders.masters.waste_masters.subproperties import SubPropertySeeder
from app.management.commands.seeders.masters.waste_masters.wastetype import WasteTypeSeeder
from app.management.commands.seeders.masters.waste_masters.bins import BinSeeder

# role-assigns (router: role-assigns/user-type, staffusertypes, contractorusertypes)
from app.management.commands.seeders.superadmin.role_management import ROLE_ASSIGN_SEEDERS

# user-creations (router: user-creations/staffcreation, supervisor-zone-map, ...)
from app.management.commands.seeders.superadmin.staff_management.auth_user_seeder import AuthUserSeeder
from app.management.commands.seeders.superadmin.staff_management.supervisor_user import SupervisorUserSeeder
from app.management.commands.seeders.core_modules.daily_operations.driver_palakkad_trips import (
    DriverPalakkadTripsSeeder,
)
from app.management.commands.seeders.superadmin.staff_management.staff_office import StaffOfficeSeeder
from app.management.commands.seeders.superadmin.staff_management.staff_personal import StaffPersonalSeeder

# transport-masters (router: transport-masters/vehicle-type, vehicle-creation, trip-attendance, fuels)
from app.management.commands.seeders.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreationSeeder
from app.management.commands.seeders.masters.transport_masters.vehicleCreation import VehicleCreationSeeder
from app.management.commands.seeders.masters.transport_masters.fuel import FuelSeeder
from app.management.commands.seeders.masters.transport_masters.trip_attendance import TripAttendanceSeeder

# process-items (router: process-items/zone-property-load-tracker)


# schedule-setup / schedule-operations (router: schedule-setup/..., schedule-operations/... —
# split from the legacy "schedule-masters" group)
from app.management.commands.seeders.core_modules.schedule_setup.collection_point import CollectionPointSeeder
from app.management.commands.seeders.core_modules.schedule_setup.staff_template import StaffTemplateSeeder
from app.management.commands.seeders.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplateSeeder
from app.management.commands.seeders.core_modules.schedule_setup.trip_plan import TripPlanSeeder
from app.management.commands.seeders.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPointSeeder
from app.management.commands.seeders.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignmentSeeder
from app.management.commands.seeders.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPointSeeder
from app.management.commands.seeders.core_modules.daily_operations.daily_trip_log import DailyTripLogSeeder
from app.management.commands.seeders.core_modules.daily_operations.bin_collection_event import BinCollectionEventSeeder
from app.management.commands.seeders.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdownSeeder
from app.management.commands.seeders.core_modules.daily_operations.waste_collection import WasteCollectionSeeder
from app.management.commands.seeders.core_modules.daily_operations.retrip_demo import RetripDemoSeeder

# screen-managements (router: screen-managements/...)
from app.management.commands.seeders.superadmin.screen_management import PERMISSION_SEEDERS

# collections (router: collections/panchayat-wise, ward-wise, zone-wise)
from app.management.commands.seeders.collections import COLLECTION_SEEDERS

# customer-masters (router: customer-masters/customercreations, ...)
from app.management.commands.seeders.masters.customer_masters import CUSTOMER_SEEDERS

# complaint-ticket (router: complaint-ticket/tickets, categories, subcategories —
# renamed from the legacy "grivences" group)
from app.management.commands.seeders.core_modules.complaint_management import (
    GRIEVANCE_SEEDERS,
    TICKET_SEEDERS,
)

# audits (router: audits/vehicle-trip-audit, trip-exception-log, ...)


# reports (router: reports/monthly-waste-comparison)
from app.management.commands.seeders.reports import REPORT_SEEDERS


# ============================================================
# SEED GROUPS — names mirror URL router groups exactly
# ============================================================

SUPERADMIN_SEEDERS = [
    *COMPANY_SEEDERS,   # company + project
    *PLATFORM_SEEDERS,  # platform users need company/project after the base data exists
]

COMMON_MASTER_SEEDERS = [
    *_COMMON_MASTER_SEEDERS,
]

MASTERS_SEEDERS = [
    *CORE_MASTER_SEEDERS,   # districts, cities, zones, wards, panchayat, etc.
    DepartmentSeeder,
    DesignationSeeder,
]

WASTE_TYPES_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
    WasteTypeSeeder,    # merged from legacy `assets` group — waste-types/wastetypes → WasteTypeViewSet
]

# Legacy alias — `assets` used to be its own URL/seed group before it was merged
# into `waste-types` (see base_urls.py). Kept pointing at the same list so old
# scripts/muscle-memory using `--group assets` keep working.
ASSETS_SEEDERS = WASTE_TYPES_SEEDERS

# Note: BinSeeder (waste-types/bins) depends on CollectionPoint (schedule-setup), so
# in `all` mode BinSeeder is invoked from within schedule-setup (after CollectionPointSeeder)
# rather than from this list. Running `--group waste-types` alone seeds WasteType only;
# bins require schedule-setup's CollectionPoints to exist first.

ROLE_ASSIGNS_SEEDERS = [
    *ROLE_ASSIGN_SEEDERS,
]

USER_CREATIONS_SEEDERS = [
    AuthUserSeeder,
    StaffOfficeSeeder,
    StaffPersonalSeeder,
    
]

TRANSPORT_MASTERS_SEEDERS = [
    VehicleTypeCreationSeeder,   # transport-masters/vehicle-type
    VehicleCreationSeeder,       # transport-masters/vehicle-creation
    FuelSeeder,                  # transport-masters/fuels
]

PROCESS_ITEMS_SEEDERS = [
    # ZonePropertyLoadTrackerSeeder,  # process-items/zone-property-load-tracker
]

# ============================================================
# SCHEDULE SETUP (router: schedule-setup/staff-templates,
# alternative-staff-templates, collection-points, trip-plans)
# BinSeeder is included here (after CollectionPointSeeder) because
# bins depend on collection_points which are seeded in this group,
# even though Bins themselves live under the waste-types URL group.
# ============================================================
SCHEDULE_SETUP_SEEDERS = [
    CollectionPointSeeder,          # 1. collection-points
    BinSeeder,                      # waste-types/bins — must follow CollectionPoint
    StaffTemplateSeeder,            # 2. staff-templates
    AlternativeStaffTemplateSeeder, # 3. alternative-staff-templates
    TripPlanSeeder,                 # 4. trip-plans
    TripPlanCollectionPointSeeder,  # 5. trip-plan-collection-points
]

# ============================================================
# SCHEDULE OPERATIONS (router: schedule-operations/daily-trip-assignments,
# daily-trip-collection-points, daily-trip-household-collections,
# bin-collection-events, daily-trip-logs, wastecollections, ...)
# ============================================================
SCHEDULE_OPERATIONS_SEEDERS = [
    DailyTripAssignmentSeeder,      # 1. daily-trip-assignments
    DailyTripCollectionPointSeeder, # 2. daily-trip-collection-points
    DailyTripLogSeeder,             # 3. daily-trip-logs
    TripAttendanceSeeder,
    BinCollectionEventSeeder,       # 4. bin-collection-events
    # Depends on driver_user (user-creations) AND today's DailyTripAssignment
    # rows (above) both existing — must run last in this group.
    SupervisorUserSeeder,
    # Builds driver_user's own bin + household trips under Blue Planet /
    # Palakkad BP (the stock plans above sit under the IWMS company, which
    # CompanyScopedViewSet hides from driver_user). Runs after
    # SupervisorUserSeeder so supervisor_user exists to own the plans.
    DriverPalakkadTripsSeeder,
]

# Legacy alias — `schedule-masters` used to cover both of the above before it was
# split into `schedule-setup` / `schedule-operations` (see base_urls.py). Kept as
# the concatenated list so old scripts/muscle-memory using `--group schedule-masters`
# keep working. NOT included in ORDERED_GROUPS/"all" to avoid double-seeding.
SCHEDULE_MASTERS_SEEDERS = [
    *SCHEDULE_SETUP_SEEDERS,
    *SCHEDULE_OPERATIONS_SEEDERS,
]

SCREEN_MANAGEMENTS_SEEDERS = [
    *PERMISSION_SEEDERS,
]

COLLECTIONS_SEEDERS = [
    *COLLECTION_SEEDERS,
]

CUSTOMER_MASTERS_SEEDERS = [
    *CUSTOMER_SEEDERS,
    # Household waste-collection records depend on customers (this group) and
    # on daily trip assignments (already seeded in schedule-operations).
    WasteCollectionSeeder,
    # Re-Trip demo scenarios also need customers (household stops) + daily
    # trip assignments (schedule-operations) to already exist.
    RetripDemoSeeder,
]

COMPLAINT_TICKET_SEEDERS = [
    *GRIEVANCE_SEEDERS,
    *TICKET_SEEDERS,
]


REPORTS_SEEDERS = [
    *REPORT_SEEDERS,
]

# ============================================================
# ORDER MATTERS — follows URL group dependency chain
# ============================================================
ORDERED_GROUPS = [
    "superadmin",           # company, project, super_admin user
    "common-masters",       # continents, countries, states
    "masters",              # districts, cities, zones, wards, panchayat, ...
    "waste-types",          # properties, subproperties, wastetypes (merged from legacy `assets`)
    "role-assigns",         # user-type, staffusertypes, contractorusertypes
    "user-creations",       # staff office, personal, auth-user, supervisor-zone-map
    "transport-masters",    # vehicle-type, vehicle-creation, fuel
    "schedule-setup",       # collection-points, bins, staff-templates, alternative-staff-templates, trip-plans
    "schedule-operations",  # daily-trip-assignments, daily-trip-collection-points, trip-logs, bin-collection-events
    "screen-managements",   # screen permissions
    "collections",          # panchayat-wise, ward-wise, zone-wise
    "customer-masters",     # customer creations, feedback, charge rules
    "complaint-ticket",     # tickets, categories, subcategories (renamed from legacy `grivences`)
    # "audits",               # vehicle-trip-audit, trip-exception-log, ...
    "reports",              # monthly-waste-comparison
]

SEED_GROUPS = {
    # Mirrors URL router group names exactly
    "superadmin":         SUPERADMIN_SEEDERS,
    "common-masters":     COMMON_MASTER_SEEDERS,
    "masters":            MASTERS_SEEDERS,
    "waste-types":        WASTE_TYPES_SEEDERS,
    "assets":             ASSETS_SEEDERS,           # legacy alias for waste-types
    "role-assigns":       ROLE_ASSIGNS_SEEDERS,
    "user-creations":     USER_CREATIONS_SEEDERS,
    "user-creation":      USER_CREATIONS_SEEDERS,   # alias
    "transport-masters":  TRANSPORT_MASTERS_SEEDERS,
    "process-items":      PROCESS_ITEMS_SEEDERS,
    "schedule-setup":     SCHEDULE_SETUP_SEEDERS,
    "schedule-operations": SCHEDULE_OPERATIONS_SEEDERS,
    "schedule-masters":   SCHEDULE_MASTERS_SEEDERS,  # legacy alias for schedule-setup + schedule-operations
    "screen-managements": SCREEN_MANAGEMENTS_SEEDERS,
    "collections":        COLLECTIONS_SEEDERS,
    "customer-masters":   CUSTOMER_MASTERS_SEEDERS,
    "customers":          CUSTOMER_MASTERS_SEEDERS,  # alias
    "complaint-ticket":   COMPLAINT_TICKET_SEEDERS,
    "grivences":          COMPLAINT_TICKET_SEEDERS,  # legacy alias for complaint-ticket
    "reports":            REPORTS_SEEDERS,
    # Legacy aliases
    "staff":              USER_CREATIONS_SEEDERS,
    "vehicles":           TRANSPORT_MASTERS_SEEDERS,
    "platform":           SUPERADMIN_SEEDERS,
    # Single-seeder shortcuts
    "bin-collection-events": [BinCollectionEventSeeder],
    "trip-logs":          [DailyTripLogSeeder],
    "vehicle-breakdowns": [VehicleBreakdownSeeder],
    "waste-collections":  [WasteCollectionSeeder],
    "retrip-demo":        [RetripDemoSeeder],
    "blue-planet":        [BluePlanetSeeder],
    "ticket-masters":     TICKET_SEEDERS,  # complaint-ticket/grievance-tickets masters only
    # Requires driver_user + today's DailyTripAssignment rows to already
    # exist (run `user-creations` and `schedule-operations` first, or `all`).
    "supervisor-user":    [SupervisorUserSeeder],
    # driver_user's bin + household trips under Blue Planet / Palakkad BP.
    "driver-trips":       [DriverPalakkadTripsSeeder],
}

# ============================================================
# EXPLICIT "ALL" GROUP — ordered for correct dependency chain
# ============================================================
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
                "Seeder group (mirrors URL router groups): "
                "superadmin | common-masters | masters | waste-types | assets (legacy alias) | "
                "role-assigns | user-creations | transport-masters | process-items | "
                "schedule-setup | schedule-operations | schedule-masters (legacy alias) | "
                "screen-managements | collections | customer-masters | "
                "complaint-ticket | grivences (legacy alias) | audits | reports | all"
            ),
        )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT == "production":
            self.stdout.write(self.style.ERROR("Seeding is disabled in PRODUCTION environment"))
            return

        if not settings.DEBUG:
            self.stdout.write(self.style.ERROR("Seeding blocked because DEBUG=False"))
            return

        group = options.get("group")

        if group:
            seeders = SEED_GROUPS.get(group)
            if not seeders:
                valid = ", ".join(k for k in SEED_GROUPS if k not in ("all",))
                self.stdout.write(self.style.ERROR(f"Invalid group '{group}'. Use one of: {valid}"))
                return
        else:
            seeders = SEED_GROUPS["all"]

        self.stdout.write(self.style.WARNING("Starting database seeding...\n"))

        for seeder_cls in seeders:
            seeder = seeder_cls()
            self.stdout.write(self.style.NOTICE(f"Running {seeder_cls.__name__}"))
            seeder.run()

        self.stdout.write(self.style.SUCCESS("\nSeeding completed successfully."))
