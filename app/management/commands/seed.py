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
# NOTE: DistrictSeeder/CitySeeder/ZoneSeeder/WardSeeder/PanchayatSeeder/
# DepartmentSeeder/DesignationSeeder all bootstrap or hardcode the generic
# "IWMS" company/project — intentionally NOT imported/registered below so
# `seed all` produces exactly one company (Blue Planet). Files remain on
# disk untouched.

# waste-types (router: waste-types/properties, subproperties, wastetypes, bins —
# wastetypes/bins merged in from the legacy "assets" group)
from app.management.commands.seeders.masters.waste_masters.properties import PropertySeeder
from app.management.commands.seeders.masters.waste_masters.subproperties import SubPropertySeeder
# WasteTypeSeeder/BinSeeder hardcode Company.objects.get(name="IWMS") —
# intentionally not imported (Blue Planet seeds its own waste types/bins).

# role-assigns (router: role-assigns/user-type, staffusertypes, contractorusertypes)
from app.management.commands.seeders.superadmin.role_management import ROLE_ASSIGN_SEEDERS

# user-creations (router: user-creations/staffcreation, supervisor-zone-map, ...)
from app.management.commands.seeders.superadmin.staff_management.auth_user_seeder import AuthUserSeeder
from app.management.commands.seeders.superadmin.staff_management.supervisor_user import SupervisorUserSeeder

# DriverWetDryBinTripsSeeder is the ONLY driver_user trip seeder. It gives
# driver_user exactly two assignments: a Wet Waste bin round and a Dry Waste
# bin round.
#
# MERGE CONFLICT RESOLUTION — READ BEFORE RESOLVING:
# Older branches import driver_palakkad_trips / driver_bin_only /
# driver_bin_assignments / driver_extra_collection_points here. Those seeders
# are DELETED — they created the household, bulk and duplicate-bin plans that
# driver_user must never have. If a merge reintroduces any of those imports,
# drop them and keep only this one; the deleted files no longer exist, so
# keeping them raises ImportError at startup.
from app.management.commands.seeders.core_modules.daily_operations.driver_wet_dry_bin_trips import (
    DriverWetDryBinTripsSeeder,
)
# StaffOfficeSeeder/StaffPersonalSeeder fall back to bootstrapping "IWMS"
# when no company exists yet — intentionally not imported/registered below
# (Blue Planet's own staff are already created inside BluePlanetSeeder).

# transport-masters (router: transport-masters/vehicle-type, vehicle-creation, trip-attendance, fuels)
from app.management.commands.seeders.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreationSeeder
# VehicleCreationSeeder (masters/transport_masters) hardcodes/bootstraps
# "IWMS" — intentionally not imported (Blue Planet seeds its own vehicles).
from app.management.commands.seeders.masters.transport_masters.fuel import FuelSeeder
from app.management.commands.seeders.masters.transport_masters.trip_attendance import TripAttendanceSeeder

# process-items (router: process-items/zone-property-load-tracker)


# schedule-setup / schedule-operations (router: schedule-setup/..., schedule-operations/... —
# split from the legacy "schedule-masters" group)
# CollectionPointSeeder/StaffTemplateSeeder/AlternativeStaffTemplateSeeder/
# TripPlanSeeder/TripPlanCollectionPointSeeder all hardcode/bootstrap "IWMS"
# — intentionally not imported (Blue Planet seeds its own collection
# points, staff templates and trip plans directly in BluePlanetSeeder).
from app.management.commands.seeders.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignmentSeeder
from app.management.commands.seeders.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPointSeeder
# DailyTripLogSeeder intentionally NOT imported/registered — DailyTripLog
# rows auto-derive from BinCollectionEvent/WasteCollection via the existing
# signal chain (sync_household_collection_on_waste_save), so seeding them
# directly is redundant. The seeder file remains on disk unwired.
from app.management.commands.seeders.core_modules.daily_operations.bin_collection_event import BinCollectionEventSeeder
from app.management.commands.seeders.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdownSeeder
from app.management.commands.seeders.core_modules.daily_operations.waste_collection import WasteCollectionSeeder
from app.management.commands.seeders.core_modules.daily_operations.retrip_demo import RetripDemoSeeder

# screen-managements (router: screen-managements/...)
from app.management.commands.seeders.superadmin.screen_management import PERMISSION_SEEDERS

# collections (router: collections/panchayat-wise, ward-wise, zone-wise)
from app.management.commands.seeders.collections import COLLECTION_SEEDERS

# customer-masters (router: customer-masters/customercreations, ...)
# CUSTOMER_SEEDERS includes CustomerCreationSeeder, which hardcodes Chennai/
# Zone 1/Ward 1 under the generic "IWMS" company — imported directly below
# and filtered down to just UserChargeRuleSeeder (company-agnostic; Blue
# Planet's own customers are created directly in BluePlanetSeeder).
from app.management.commands.seeders.masters.customer_masters.userChargeRule import UserChargeRuleSeeder

# complaint-ticket (router: complaint-ticket/tickets, categories, subcategories —
# renamed from the legacy "grivences" group)
from app.management.commands.seeders.core_modules.complaint_management import (
    GRIEVANCE_SEEDERS,
    TICKET_SEEDERS,
)

# audits (router: audits/vehicle-trip-audit, trip-exception-log, ...)


# reports (router: reports/monthly-waste-comparison)
# DailyWasteComparisonSeeder/MonthlyWasteComparisonSeeder both hardcode
# Company.objects.get(name="IWMS") — intentionally not imported below.


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

# District/City/Zone/Ward/Panchayat/Department/Designation are all seeded
# directly inside BluePlanetSeeder (superadmin group) — this group is
# intentionally empty now that the generic IWMS masters seeders are
# unregistered.
MASTERS_SEEDERS = []

WASTE_TYPES_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
    # WasteTypeSeeder dropped — Blue Planet seeds its own waste types.
]

# Legacy alias — `assets` used to be its own URL/seed group before it was merged
# into `waste-types` (see base_urls.py). Kept pointing at the same list so old
# scripts/muscle-memory using `--group assets` keep working.
ASSETS_SEEDERS = WASTE_TYPES_SEEDERS

ROLE_ASSIGNS_SEEDERS = [
    *ROLE_ASSIGN_SEEDERS,
]

USER_CREATIONS_SEEDERS = [
    AuthUserSeeder,
    # StaffOfficeSeeder/StaffPersonalSeeder dropped — Blue Planet's staff
    # are already created inside BluePlanetSeeder.
]

TRANSPORT_MASTERS_SEEDERS = [
    VehicleTypeCreationSeeder,   # transport-masters/vehicle-type
    # VehicleCreationSeeder dropped — Blue Planet seeds its own vehicles.
    FuelSeeder,                  # transport-masters/fuels
]

PROCESS_ITEMS_SEEDERS = [
    # ZonePropertyLoadTrackerSeeder,  # process-items/zone-property-load-tracker
]

# ============================================================
# SCHEDULE SETUP (router: schedule-setup/staff-templates,
# alternative-staff-templates, collection-points, trip-plans)
# Collection points, bins, staff templates and trip plans are all seeded
# directly inside BluePlanetSeeder (superadmin group) — this group is
# intentionally empty now that the generic IWMS seeders are unregistered.
# ============================================================
SCHEDULE_SETUP_SEEDERS = []

# ============================================================
# SCHEDULE OPERATIONS (router: schedule-operations/daily-trip-assignments,
# daily-trip-collection-points, daily-trip-household-collections,
# bin-collection-events, daily-trip-logs, wastecollections, ...)
# ============================================================
SCHEDULE_OPERATIONS_SEEDERS = [
    DailyTripAssignmentSeeder,      # 1. daily-trip-assignments
    DailyTripCollectionPointSeeder, # 2. daily-trip-collection-points
    # DailyTripLogSeeder dropped — trip logs auto-derive from
    # BinCollectionEvent/WasteCollection, seeding them directly is redundant.
    TripAttendanceSeeder,
    BinCollectionEventSeeder,       # 3. bin-collection-events
    # Best-effort here: on a fresh DB, driver_user has no trip yet at this
    # point (DriverWetDryBinTripsSeeder below creates it), so this just logs
    # "no trip today — Skipping" without creating supervisor_user. That's
    # fine — DriverWetDryBinTripsSeeder creates the login itself if it's
    # still missing when it runs. Kept here (rather than removed) so a
    # RE-run of `seed all`, once driver_user already has a trip, has this
    # seeder do its normal trip-plan-ownership wiring/refresh too.
    SupervisorUserSeeder,
    # driver_user's own bin-collection trips — one Wet Waste round, one Dry
    # Waste round, 10 collection points each, supervised by supervisor_user.
    # Self-contained: creates supervisor_user itself if SupervisorUserSeeder
    # above couldn't (see the seeder's own module docstring for why).
    # Replaces the removed DriverPalakkadTripsSeeder/DriverBinOnlySeeder/
    # DriverBinAssignmentsSeeder (and their `driver-trips`/`driver-bin-only`/
    # `driver-bin-assignments` standalone shortcuts) which used to seed
    # driver_user's trips — those were unwired on request so a fresh DB
    # started with zero trips; this is the new, deliberate replacement.
    DriverWetDryBinTripsSeeder,
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
    # CustomerCreationSeeder dropped — Blue Planet's own customers are
    # created directly inside BluePlanetSeeder. UserChargeRuleSeeder is
    # company-agnostic (picks up whichever company exists) and kept.
    UserChargeRuleSeeder,
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


# DailyWasteComparisonSeeder/MonthlyWasteComparisonSeeder both hardcode the
# generic "IWMS" company — intentionally left unregistered.
REPORTS_SEEDERS = []

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
    "vehicle-breakdowns": [VehicleBreakdownSeeder],
    # driver_user's Wet/Dry bin-collection trips (see the seeder's own
    # module docstring). Requires the superadmin group (Blue Planet masters)
    # and user-creations (driver_user/operator_user) to have run first.
    "driver-wet-dry-bin-trips": [DriverWetDryBinTripsSeeder],
    "waste-collections":  [WasteCollectionSeeder],
    "retrip-demo":        [RetripDemoSeeder],
    "blue-planet":        [BluePlanetSeeder],
    "ticket-masters":     TICKET_SEEDERS,  # complaint-ticket/grievance-tickets masters only
    # Requires driver_user + today's DailyTripAssignment rows to already
    # exist (run `user-creations` and `schedule-operations` first, or `all`).
    # driver_user currently has no seeded trips, so this is a no-op until
    # some other seeder gives it one.
    "supervisor-user":    [SupervisorUserSeeder],
    # driver_user's own trip seeders (formerly `driver-trips`,
    # `driver-bin-only`, `driver-bin-assignments`) were removed on request —
    # a fresh DB + `seed all` leaves driver_user with zero trips for now.
    # The seeder source files are left in place, just unwired from every
    # group/shortcut here, in case they're wanted again later.
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
