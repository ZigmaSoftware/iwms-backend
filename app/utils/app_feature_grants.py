"""Mobile app modules, and what each mobile screen needs to be visible.

There is ONE permission list. A screen ticked on a Staff Access Configuration
grants that screen in web and in the mobile app identically — the middleware
authorizes both from the same rows, so an admin never has to reason about two
parallel namespaces.

Two things sit alongside that single list:

* **App modules** decide which app a person may sign into at all. They are a
  master (`AppModule`) ticked on the access configuration, not a screen
  permission, because "may open the Driver app" is not an API call.

* **Screen visibility** is a code-owned map from each mobile screen to the ONE
  permission that governs whether it appears. A mobile screen usually reads
  several endpoints, but gating on all of them would mean a missed tick makes a
  tab silently vanish, so only its main list permission decides. Anything else
  it cannot read is hidden inside the screen instead.

Citizens are the one exception: every citizen route is middleware-exempt and
hard-scoped to the logged-in customer, so there is nothing in the permission
catalog to grant them. Their three app screens are ticked on a
CustomerAccessConfiguration and gate the app's UI only.
"""

# ============================================================
# APP MODULES
# ============================================================
# Seeded into the AppModule master. `module_key` and `route` are read-only in
# web because the screens and routes behind them ship inside the Flutter build.

APP_MODULE_SEED = [
    {
        "module_key": "app-citizen",
        "surface_key": "citizen",
        "label": "Customer",
        "route": "/citizen/home",
        "order_no": 1,
        "description": "Citizen app — complaints, collection history, profile.",
    },
    {
        "module_key": "app-driver",
        "surface_key": "driver",
        "label": "Driver",
        "route": "/driver/home",
        "order_no": 2,
        "description": "Driver (Captain) app — trips, households, bins, breakdowns.",
    },
    {
        "module_key": "app-operator",
        "surface_key": "operator",
        "label": "Operator",
        "route": "/operator/home",
        "order_no": 3,
        "description": "Operator app. Merged into the Driver shell; kept for existing logins.",
    },
    {
        "module_key": "app-supervisor",
        "surface_key": "supervisor",
        "label": "Supervisor",
        "route": "/supervisor/home",
        "order_no": 4,
        "description": "Supervisor app — trips, crew, complaints, re-trips, breakdowns.",
    },
]

APP_MODULE_KEYS = tuple(entry["module_key"] for entry in APP_MODULE_SEED)
APP_SURFACE_KEYS = tuple(entry["surface_key"] for entry in APP_MODULE_SEED)

# Choices for the "App Module" field on the staff/customer creation forms. The
# field picks the app a user lands in; the ticks decide which they may open.
APP_MODULE_CHOICES = tuple(
    (entry["surface_key"], entry["label"]) for entry in APP_MODULE_SEED
) + (("none", "No App Access"),)

APP_SURFACE_CONFIG = {
    entry["surface_key"]: {"label": entry["label"], "route": entry["route"]}
    for entry in APP_MODULE_SEED
}


# ============================================================
# CITIZEN APP SCREENS
# ============================================================
# The exception described above. These are real UserScreen rows under the
# "app-citizen" MainScreen, ticked on a CustomerAccessConfiguration.

CITIZEN_APP_MAINSCREEN = "app-citizen"

CITIZEN_APP_SCREENS = [
    "app-citizen-complaints",
    "app-citizen-collections",
    "app-citizen-profile",
]


# ============================================================
# SCREEN VISIBILITY
# ============================================================
# mobile screen key -> the single (module, screen, action) that makes it appear.
# `None` means the screen is always available: it is the user's own profile,
# which nobody should be locked out of once they are already signed in.
# Attendance and operator-mobile trip/scan routes are protected by
# ModulePermissionMiddleware and map back to Staff Access Configuration
# permissions.
#
# The keys are the same strings the Flutter build uses — see
# lib/core/permissions/app_screens.dart. The two must stay in step, and
# tests/test_app_feature_grants.py fails if a permission named here does not
# exist in the router.

SCREEN_PERMISSIONS = {
    # ---- Supervisor ----
    "supervisor.dashboard": ("schedule-operations", "daily-trip-assignments", "view"),
    "supervisor.trips": ("schedule-operations", "daily-trip-assignments", "view"),
    "supervisor.crew": ("schedule-setup", "staff-templates", "view"),
    "supervisor.households": ("customers", "customercreations", "view"),
    "supervisor.waste": ("schedule-operations", "wastecollections", "view"),
    "supervisor.breakdowns": ("schedule-operations", "vehicle-breakdowns", "view"),
    "supervisor.retrips": ("schedule-operations", "retrip-requests", "view"),
    "supervisor.complaints": ("complaint-ticket", "tickets", "view"),
    "supervisor.notifications": ("schedule-operations", "staff-notifications", "view"),
    "supervisor.livemap": ("schedule-operations", "daily-trip-collection-points", "view"),
    "supervisor.vehicles": ("transport-masters", "vehicle-creation", "view"),
    "supervisor.attendance": ("attendance", "attendance", "view"),
    "supervisor.profile": None,

    # ---- Driver ----
    "driver.trips": ("schedule-operations", "daily-trip-assignments", "view"),
    "driver.households": ("schedule-operations", "daily-trip-household-collections", "view"),
    "driver.bins": ("schedule-operations", "bin-collection-events", "view"),
    "driver.breakdowns": ("schedule-operations", "vehicle-breakdowns", "view"),
    "driver.delays": ("schedule-operations", "trip-delay-reports", "view"),
    "driver.retrips": ("schedule-operations", "retrip-requests", "view"),
    "driver.notifications": ("schedule-operations", "staff-notifications", "view"),
    "driver.customers": ("customers", "customercreations", "view"),
    "driver.attendance": ("attendance", "attendance", "view"),
    "driver.profile": None,

    # ---- Operator (deprecated shell, same permissions as Driver) ----
    "operator.trips": ("schedule-operations", "daily-trip-assignments", "view"),
    "operator.households": ("schedule-operations", "daily-trip-household-collections", "view"),
    "operator.bins": ("schedule-operations", "bin-collection-events", "view"),
    "operator.breakdowns": ("schedule-operations", "vehicle-breakdowns", "view"),
    "operator.notifications": ("schedule-operations", "staff-notifications", "view"),
    "operator.attendance": ("attendance", "attendance", "view"),
    "operator.profile": None,

    # ---- Citizen ----
    # Ticked per customer on a CustomerAccessConfiguration instead; these carry
    # no module permission because the citizen routes need none.
    "citizen.complaints": None,
    "citizen.collections": None,
    "citizen.profile": None,
}


def visible_screens(permissions, surface, citizen_screens=None):
    """Which screens of `surface` the user can see, given their permissions.

    Returns the screen keys the app should render. A screen whose governing
    permission is absent is left out; a screen with no governing permission is
    always included.
    """
    from app.middleware.module_permission_middleware import (
        MODULE_PERMISSION_ALIASES,
    )

    prefix = f"{surface}."
    granted = []

    for screen_key, requirement in SCREEN_PERMISSIONS.items():
        if not screen_key.startswith(prefix):
            continue

        if requirement is None:
            if surface == "citizen" and citizen_screens is not None:
                # Citizen screens are ticked explicitly, so an empty selection
                # means nothing is shown rather than everything.
                name = f"app-citizen-{screen_key.split('.', 1)[1]}"
                if name not in citizen_screens:
                    continue
            granted.append(screen_key)
            continue

        module, screen, action = requirement
        actions = (permissions or {}).get(module, {}).get(screen)
        if actions is None:
            alias = MODULE_PERMISSION_ALIASES.get(module)
            if alias:
                actions = (permissions or {}).get(alias, {}).get(screen)
        if actions and action in actions:
            granted.append(screen_key)

    return granted


# ============================================================
# ROLE SCREEN TEMPLATES
# ============================================================
# The screens each app role actually calls. NOT a runtime baseline — nothing
# is granted implicitly any more, because a baseline underneath the ticks meant
# unticking a screen changed nothing.
#
# These back two things instead: the "Apply defaults" button on the access
# configuration form, and `manage.py backfill_app_access`. Every entry is an
# ordinary screen an admin could tick by hand; the template only saves them
# knowing which screens the Driver app happens to read.
#
# tests/test_app_feature_grants.py fails if any screen named here is not a real
# route the middleware would accept.

ROLE_SCREEN_TEMPLATES = {
    # Driver ("captain") — the driver and operator apps are merged, so this
    # role also drives trips end to end: read its own assignments/stops and
    # write collection progress. The operator-mobile/* endpoints are mobile
    # routes, but the middleware maps them back to these Daily Operations
    # resources.
    "driver": {
        "customers": {
            "customercreations": ["view"],
        },
        "schedule-operations": {
            "daily-trip-assignments": ["view", "edit"],
            "daily-trip-collection-points": ["view", "edit"],
            "daily-trip-household-collections": ["view", "edit"],
            "bin-collection-events": ["view", "add"],
            "daily-trip-logs": ["view", "add", "edit"],
            "vehicle-breakdowns": ["view", "add"],
            "trip-delay-reports": ["view", "add"],
            # Mark-as-read is a POST -> "add", not "edit".
            "staff-notifications": ["view", "add", "edit"],
            # Read-only: the driver app shows its own Re-Trip request's
            # status while a supervisor decides it, but never approves/
            # rejects/creates one directly — that's all via retrip_service.
            "retrip-requests": ["view"],
        },
        "attendance": {
            "attendance": ["view", "add", "edit"],
        },
        "schedule-setup": {
            "collection-points": ["view"],
        },
        # The trip header shows the assigned vehicle, and the breakdown flow
        # reads the vehicle detail before reporting against it.
        "transport-masters": {
            "vehicle-creation": ["view"],
            "vehicle-type": ["view"],
        },
    },
    "operator": {
        "customers": {
            "customercreations": ["view"],
        },
        "schedule-operations": {
            "daily-trip-assignments": ["view", "edit"],
            "daily-trip-collection-points": ["view", "edit"],
            "daily-trip-household-collections": ["view", "edit"],
            "bin-collection-events": ["view", "add"],
            "daily-trip-logs": ["view", "add", "edit"],
            "vehicle-breakdowns": ["view", "add"],
            "trip-delay-reports": ["view", "add"],
            # Mark-as-read is a POST -> "add", not "edit".
            "staff-notifications": ["view", "add", "edit"],
            "retrip-requests": ["view"],
        },
        "attendance": {
            "attendance": ["view", "add", "edit"],
        },
        "schedule-setup": {
            "collection-points": ["view"],
        },
        # The trip header shows the assigned vehicle, and the breakdown flow
        # reads the vehicle detail before reporting against it.
        "transport-masters": {
            "vehicle-creation": ["view"],
            "vehicle-type": ["view"],
        },
    },
    # Backs the supervisor app (module5_supervisor): assignments/trip logs
    # for the home + trips screens, staff + templates for the crew/teams
    # screens, collection points and customers for the households screen,
    # grievance tickets for the supervisor grievance view.
    "supervisor": {
        "schedule-operations": {
            # The crew-substitution flow PATCHes the assignment, so "view"
            # alone 403s the moment a supervisor applies a substitute.
            "daily-trip-assignments": ["view", "edit"],
            "daily-trip-logs": ["view"],
            "daily-trip-collection-points": ["view"],
            "daily-trip-household-collections": ["view"],
            "vehicle-breakdowns": ["view", "edit"],
            "trip-delay-reports": ["view", "edit"],
            # Mark-as-read and mark-all-read are POSTs, which
            # HTTP_ACTION_MAP scores as "add" — "edit" never authorized them.
            "staff-notifications": ["view", "add", "edit"],
            "bin-collection-events": ["view"],
            # Household waste collections (WasteCollection model) — the
            # supervisor waste-summary cards' `mine=true` fetch needs this
            # alongside bin-collection-events, or every household collection
            # a driver makes is silently invisible to the dashboard (only
            # bin scans were ever visible before this was added).
            "wastecollections": ["view"],
            # Reviews Re-Trip requests via the approve/reject actions —
            # both POST, so the middleware's HTTP_ACTION_MAP scores them as
            # "add", not "edit"; create/update/destroy stay disabled in the
            # viewset itself so nothing else can write here.
            "retrip-requests": ["view", "add"],
        },
        "attendance": {
            "attendance": ["view", "add", "edit"],
        },
        "schedule-setup": {
            # The Crew screen creates and edits templates, and creates an
            # alternative template when substituting a crew member.
            "staff-templates": ["view", "add", "edit"],
            "alternative-staff-templates": ["view", "add"],
            "collection-points": ["view"],
            "trip-plans": ["view"],
        },
        "staff-creations": {
            "staffcreation": ["view"],
        },
        "customers": {
            "customercreations": ["view"],
        },
        "transport-masters": {
            "vehicle-creation": ["view"],
        },
        "complaint-ticket": {
            # Every ticket action (resolve/escalate/assign/comments/
            # attachments/reopen/feedback/status) is a POST, so the
            # middleware's HTTP_ACTION_MAP scores them "add", not "edit" —
            # a plain PATCH/PUT on the ticket resource itself is the only
            # thing "edit" actually gates here.
            "grievance-tickets": ["view", "edit", "add"],
            "tickets": ["view", "edit", "add"],
        },
    },
}
