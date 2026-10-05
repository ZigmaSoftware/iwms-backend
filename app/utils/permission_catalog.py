"""The permission catalog: ONE definition of every module and screen.

Everything that names a permission reads it from here:

- the permission seeder creates MainScreenType / MainScreen / UserScreen rows
  from SECTIONS (seeders/superadmin/screen_management/permissions.py);
- the permission forms show `label` and group screens by `group`
  (via app/utils/screen_dependencies.py);
- ModulePermissionMiddleware authorizes each URL route listed under a screen's
  `routes` with that screen's grant (ROUTE_OWNERS);
- the frontend sidebar imports the generated copy,
  iwms-frontend/src/generated/permissionCatalog.ts, so a wrong module/screen
  name there is a TypeScript error.

After editing this file run:

    python manage.py sync_permission_catalog

which rewrites the frontend copy (tests fail while it is stale), then re-run
the permission seeder so the new screens exist in the database. Until it is
seeded a screen is missing from the permission forms; the sync command warns
about any catalog screen this database has no row for.

Naming rules
------------
- A module's `name` is the MainScreen name (the permission key). `url_module`
  is the router group in app/urls/base_urls.py when that differs.
- A screen's `name` is the UserScreen name. Its routes default to
  "<url_module>/<name>". Give `routes` explicitly when the router uses another
  path, when one page calls several routes, or `()` for a frontend-only page.
  A bare route is relative to the module's url_module; "module/route" is
  absolute (e.g. the driver app's "operator-mobile/..." routes).
- Child APIs a page writes through, and dropdown sources it reads, belong in
  SCREEN_DEPENDENCIES (screen_dependencies.py), not here.
- `group` puts screens under one heading in the permission forms (one sidebar
  page backed by several screens). Ticking the heading ticks every screen.
- Never rename a `name` casually: grants are stored against it. Renaming needs
  a migration or seeder step that moves the existing rows.
- Splitting a page out of an existing screen? Give the new screen
  `inherits_grants_from="<old screen>"`: when the seeder first creates it, it
  copies the old screen's company and staff grants, so nobody loses access.
"""


def screen(name, label, *, routes=None, group=None, inherits_grants_from=None):
    return {
        "name": name,
        "label": label,
        "routes": routes,
        "group": group,
        "inherits_grants_from": inherits_grants_from,
    }


def module(name, label, screens, *, url_module=None):
    return {
        "name": name,
        "label": label,
        "url_module": url_module or name,
        "screens": screens,
    }


GROUP_LABELS = {
    "daily-trip-plan": "Daily Trip Plan",
    "staff-user-type": "Staff User Type",
    "weighbridge-management": "Weighbridge Management",
    "complaint-types": "Complaint Types",
    "complaint-desk": "Complaint Desk",
}


# (MainScreenType name, modules) in sidebar order. The citizen app screens
# ("mobile-app") are added by the seeder from app_feature_grants.py: they gate
# the citizen app only and have no web page.
SECTIONS = (
    ("super-admin", (
        # Platform routes ("superadmin/...") are not module-gated.
        module("superadmin-masters", "SuperAdmin Masters", (
            screen("company", "Company", routes=()),
            screen("project", "Project", routes=()),
        )),
        module("screen-managements", "Screen Management", (
            screen("mainscreentype", "MainScreen Type"),
            screen("mainscreens", "MainScreen"),
            screen("userscreens", "User Screen"),
            screen("userscreen-action", "UserScreen Action"),
            # The page also saves column permissions.
            screen(
                "companywisescreenpermissions",
                "Companywise User Screen Permission",
                routes=("companywisescreenpermissions", "column-permissions"),
            ),
            screen("app-modules", "App Modules"),
        )),
        module("role-assigns", "Role Management", (
            screen("user-type", "User Type"),
            # Two tabs of one page.
            screen("staffusertypes", "Staff User Type", group="staff-user-type"),
            screen("contractorusertypes", "Contractor User Type", group="staff-user-type"),
            screen("project-staff-hierarchy", "Project Staff Hierarchy"),
        )),
        module("staff-creations", "Staff Management", (
            screen("department-masters", "Department Master", routes=("departments",)),
            screen("designation-masters", "Designation Master", routes=("designations",)),
            screen("staffcreation", "Staff Creation"),
            screen("staff-access-configuration", "Staff Access Configuration"),
        )),
        module("common-masters", "Common Masters", (
            screen("continents", "Continent"),
            screen("countries", "Country"),
            screen("states", "State"),
        )),
        # Global complaint configuration (no company/project FK). Only the
        # Complaint Types page's tabs are grantable; the other reference
        # tables are seeder-owned (SUPERADMIN_ONLY_ROUTES).
        module("complaint-masters", "Complaint Masters", (
            screen("types", "Types", group="complaint-types"),
            screen("categories", "Categories", group="complaint-types"),
            screen("subcategories", "Subcategories", group="complaint-types"),
            screen("sla-rules", "SLA Rules", group="complaint-types"),
        )),
        module("audits", "Audits", (
            screen("common-audit", "Common Audit"),
            screen("login-audit", "Login Audit"),
            screen("permission-audit", "User Access Audit"),
            screen("static-route-audit", "Static Route Audit"),
            screen("complaint-audit", "Complaint Audit"),
        )),
    )),
    ("masters", (
        # The sidebar shows these as two menus.
        module("masters", "Location Masters / Leader Management", (
            screen("districts", "District"),
            screen("cities", "City"),
            screen("zones", "Zone"),
            screen("wards", "Ward"),
            screen("panchayat", "PLB (Participating Local Bodies)"),
            screen("panchayat-leaders", "PLB Leader"),
            screen("district-leaders", "District Leader"),
            screen("plants", "Plant"),
        )),
        module("waste-types", "Waste Masters", (
            screen("properties", "Property"),
            screen("subproperties", "SubProperty"),
            screen("bins", "Bin Creation"),
            screen("waste type", "Waste Type", routes=("wastetypes",)),
        )),
        module("transport-masters", "Transport Masters", (
            screen("vehicle-type", "Vehicle Type"),
            screen("vehicle-creation", "Vehicle Creation"),
            screen("fuels", "Fuel"),
        )),
        module("customers", "Customer Masters", (
            screen("customercreations", "Customer Creation"),
            screen("customer-access-configuration", "Customer App Access"),
            # Reads the customer list (SCREEN_DEPENDENCIES lookup).
            screen("apartment-list", "Apartment List", routes=()),
        ), url_module="customer-masters"),
    )),
    ("core-modules", (
        module("schedule-setup", "Schedule Setup", (
            screen("staff-templates", "Staff Template"),
            screen("alternative-staff-templates", "Alternative Staff Template"),
            screen("collection-points", "Collection Point"),
            screen("trip-plans", "Trip Plans"),
        )),
        module("schedule-operations", "Daily Operations", (
            screen(
                "daily-trip-assignments", "Trip Assignments",
                group="daily-trip-plan",
                routes=(
                    "daily-trip-assignments",
                    "operator-mobile/my-trip-today",
                    "operator-mobile/my-trips-today",
                    "operator-mobile/trip-history",
                    "operator-mobile/trip-lifecycle",
                ),
            ),
            screen(
                "daily-trip-collection-points",
                "Trip Collection Points",
                group="daily-trip-plan",
                routes=(
                    "daily-trip-collection-points",
                    "operator-mobile/validate-bin-qr",
                ),
            ),
            screen(
                "daily-trip-household-collections", "Household Collection Points",
                group="daily-trip-plan",
            ),
            # Read-only page over the trip collection points' tracking
            # actions (SCREEN_DEPENDENCIES lookups). Was opened by the
            # daily-trip-collection-points grant, hence the inherited grants.
            screen(
                "daily-trip-tracking", "Daily Trip Tracking",
                routes=(), inherits_grants_from="daily-trip-collection-points",
            ),
            # Saves through route-detour-waypoints / trip-plan-static-routes
            # (SCREEN_DEPENDENCIES includes).
            screen("static-route-map", "Static Route Map", routes=()),
            screen(
                "bin-collection-events", "Secondary Bin Collection Event",
                routes=("bin-collection-events", "operator-mobile/scan-bin"),
            ),
            screen("daily-trip-logs", "Daily Trip Logs"),
            screen("wastecollections", "Household Collections"),
            screen("vehicle-breakdowns", "Vehicle Breakdown"),
            screen("trip-delay-reports", "Trip Delays"),
            screen("retrip-requests", "Re-Trip Requests"),
            screen("staff-notifications", "Staff Notifications (mobile app)"),
        )),
        module("complaint-ticket", "Complaint Management", (
            screen(
                "tickets", "Tickets",
                group="complaint-desk",
                # The mobile app calls the alias route.
                routes=("tickets", "grievance-tickets"),
            ),
            screen("reopen-history", "Reopen History", group="complaint-desk"),
            screen("address-change", "Address Change Requests", group="complaint-desk"),
            screen("notifications", "Ticket Notifications", group="complaint-desk"),
            # Frontend page over the tickets API.
            screen("my-tasks", "My Tasks", routes=()),
            screen("feedback", "Feedback"),
        )),
        module("attendance", "Attendance", (
            screen(
                "attendance", "Attendance",
                routes=(
                    "external-records",
                    "daily-attendance",
                    "staff-profile",
                    "register",
                    "recognize",
                    "records",
                ),
            ),
        )),
    )),
    ("reports", (
        module("reports", "Waste & Complaint Reports", (
            screen("daily-waste-comparisons", "Daily Waste Comparison"),
            screen("monthly-waste-comparison", "Monthly Waste Comparison"),
            # Shown in the sidebar under Complaint Management.
            screen("complaints-report", "Complaints Report"),
        )),
        # GPS pages served by an external tracker: no backend routes.
        module("fleet-reports", "Fleet & Reports", (
            screen("vehicle-track", "Vehicle Tracking", routes=()),
            screen("vehicle-history", "Vehicle History", routes=()),
            screen("trip-summary", "Trip Summary", routes=()),
            screen("monthly-distance", "Monthly Distance", routes=()),
            screen("waste-collected-summary", "Waste Collected Summary", routes=()),
            screen(
                "weighbridge-management", "Weighbridge Management",
                routes=(), group="weighbridge-management",
            ),
            screen("date-report", "Date Report", routes=(), group="weighbridge-management"),
            screen("day-report", "Day Report", routes=(), group="weighbridge-management"),
        )),
    )),
)


# Protected routes deliberately granted to no screen: only a superuser
# reaches them. Listed so the route audit test can tell "intentional" from
# "forgotten".
SUPERADMIN_ONLY_ROUTES = frozenset({
    # Seeder-owned complaint vocabularies the routing/SLA resolvers key on.
    "complaint-masters/routing-rules",
    "complaint-masters/modules",
    "complaint-masters/priorities",
    "complaint-masters/statuses",
    "complaint-masters/sources",
    "complaint-masters/languages",
    # Read-only mirrors with no web page using them yet. Add them to a
    # screen's SCREEN_DEPENDENCIES lookups when a page needs one.
    "complaint-ticket/languages",
    "complaint-ticket/ticket-categories",
    "complaint-ticket/ticket-subcategories",
    "complaint-ticket/sla-rules",
    "complaint-ticket/routing-rules",
})

# Protected routes the middleware lets through on authentication alone
# (see the `endswith` bypasses in module_permission_middleware.py).
AUTH_ONLY_ROUTES = frozenset({
    "attendance/face-config",
})


# ------------------------------------------------------------------
# Derived views — use these rather than walking SECTIONS yourself.
# ------------------------------------------------------------------

MODULES = {m["name"]: m for _, modules in SECTIONS for m in modules}

# {mainscreen: [userscreen, ...]} in sidebar order.
SCREEN_STRUCTURE = {
    name: [s["name"] for s in m["screens"]] for name, m in MODULES.items()
}

# {mainscreentype: (mainscreen, ...)}
SECTION_MODULES = {
    section: tuple(m["name"] for m in modules) for section, modules in SECTIONS
}

MAINSCREEN_LABELS = {name: m["label"] for name, m in MODULES.items()}

SCREEN_LABELS = {
    s["name"]: s["label"] for m in MODULES.values() for s in m["screens"]
}

SCREEN_GROUPS = {
    key: {
        "label": label,
        "screens": tuple(
            s["name"]
            for m in MODULES.values()
            for s in m["screens"]
            if s["group"] == key
        ),
    }
    for key, label in GROUP_LABELS.items()
}


def screen_routes(mod, scr):
    """Full "<url-module>/<route>" keys a screen owns."""
    routes = (scr["name"],) if scr["routes"] is None else scr["routes"]
    return tuple(r if "/" in r else f"{mod['url_module']}/{r}" for r in routes)


def _route_owners():
    owners = {}
    for m in MODULES.values():
        for s in m["screens"]:
            for route in screen_routes(m, s):
                if route in owners:
                    raise ValueError(
                        f"Route {route!r} is owned by both {owners[route]} and "
                        f"{(m['name'], s['name'])}; a route has one owner."
                    )
                owners[route] = (m["name"], s["name"])
    return owners


# "<url-module>/<route>" -> (mainscreen, userscreen) whose grant authorizes it.
ROUTE_OWNERS = _route_owners()

# New userscreen -> userscreen whose grants it copies when first seeded.
INHERITS_GRANTS_FROM = {
    s["name"]: s["inherits_grants_from"]
    for m in MODULES.values()
    for s in m["screens"]
    if s["inherits_grants_from"]
}
