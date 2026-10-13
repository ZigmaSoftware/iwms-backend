"""APIs a screen calls besides its own, so one checkbox covers the whole page.

The permission catalog has one UserScreen per backend resource, but a web
screen is often built from several: the Daily Trip Assignment form also saves
the trip's household stops, and nearly every form fills its dropdowns from
other masters. Without this map an admin has to tick every one of those
resources as well, and nothing tells them which.

Keyed by the owning screen as (mainscreen_name, userscreen_name) — the same
names the permission seeder creates and Staff Access Configuration ticks.
Resources are "<url-module>/<route>", exactly as the frontend's
`adminEndpoints` spells them.

- "includes": child resources the screen's own form writes through. A grant on
  the owner authorizes the SAME action on them (edit owner -> edit child).
- "lookups": dropdown / reference sources. Any grant on the owner authorizes a
  read of them, never a write — writes still need the resource's own screen.

Only protected modules matter here (see MODULE_RESOURCE_ALLOWLIST in
module_permission_middleware.py); `superadmin/*` and the other
unprotected groups are reachable by any authenticated user already.
"""

from app.utils import permission_catalog as _catalog

_LOCATION_LOOKUPS = (
    "common-masters/continents",
    "common-masters/countries",
    "common-masters/states",
    "masters/districts",
    "masters/cities",
    "masters/zones",
    "masters/wards",
    "masters/panchayat",
)

_COMPLAINT_MASTER_LOOKUPS = (
    "complaint-ticket/modules",
    "complaint-ticket/categories",
    "complaint-ticket/subcategories",
    "complaint-ticket/priorities",
    "complaint-ticket/sources",
    "complaint-ticket/statuses",
    "role-assigns/project-staff-hierarchy",
    "staff-creations/departments",
)

SCREEN_DEPENDENCIES = {
    # ---------------- masters ----------------
    ("common-masters", "states"): {
        "lookups": ("common-masters/countries",),
    },
    ("masters", "zones"): {"lookups": _LOCATION_LOOKUPS},
    ("masters", "wards"): {"lookups": _LOCATION_LOOKUPS},
    ("masters", "panchayat"): {"lookups": _LOCATION_LOOKUPS},
    ("masters", "panchayat-leaders"): {"lookups": ("masters/panchayat",)},
    ("masters", "district-leaders"): {"lookups": ("masters/districts",)},
    ("waste-types", "bins"): {
        "lookups": _LOCATION_LOOKUPS + (
            "schedule-setup/collection-points",
            "waste-types/wastetypes",
        ),
    },
    ("customers", "customercreations"): {
        "lookups": _LOCATION_LOOKUPS + (
            "waste-types/properties",
            "waste-types/subproperties",
            "waste-types/wastetypes",
            "screen-managements/app-modules",
        ),
    },
    # Its own sidebar page, but it only reads the customer list (and its
    # apartment-count action) — no screen of its own on the backend router.
    ("customers", "apartment-list"): {
        "lookups": ("customer-masters/customercreations",),
    },

    # ---------------- role / staff setup ----------------
    # Staff and contractor user types are two tabs of one page, shown as one
    # "Staff User Type" row (SCREEN_GROUPS below).
    ("role-assigns", "staffusertypes"): {
        "lookups": ("role-assigns/user-type",),
    },
    ("role-assigns", "contractorusertypes"): {
        "lookups": ("role-assigns/user-type",),
    },
    ("role-assigns", "project-staff-hierarchy"): {
        "lookups": ("role-assigns/staffusertypes",),
    },
    ("staff-creations", "designation-masters"): {
        "lookups": ("staff-creations/departments",),
    },
    ("staff-creations", "staffcreation"): {
        "lookups": (
            "staff-creations/departments",
            "staff-creations/designations",
            "role-assigns/staffusertypes",
            "role-assigns/contractorusertypes",
            "screen-managements/app-modules",
        ),
    },
    ("staff-creations", "staff-access-configuration"): {
        "lookups": _LOCATION_LOOKUPS + (
            "role-assigns/user-type",
            "role-assigns/staffusertypes",
        ),
    },

    # ---------------- schedule setup ----------------
    ("schedule-setup", "staff-templates"): {
        "lookups": ("staff-creations/staffcreation",),
    },
    ("schedule-setup", "alternative-staff-templates"): {
        "lookups": (
            "schedule-setup/staff-templates",
            "staff-creations/staffcreation",
        ),
    },
    ("schedule-setup", "collection-points"): {"lookups": _LOCATION_LOOKUPS},

    # ---------------- daily operations ----------------
    # Its stops (household collections, collection points) are separate
    # screens in the "Daily Trip Plan" group below, ticked alongside it.
    ("schedule-operations", "daily-trip-assignments"): {
        "lookups": (
            "customer-masters/customercreations",
            "waste-types/bins",
        ),
    },
    ("schedule-operations", "daily-trip-collection-points"): {
        "lookups": (
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/route-detour-waypoints",
            "schedule-setup/staff-templates",
            "schedule-setup/alternative-staff-templates",
            "schedule-setup/collection-points",
            "staff-creations/staffcreation",
            "waste-types/bins",
            "masters/plants",
            "masters/zones",
            "masters/wards",
            "masters/panchayat",
        ),
    },
    # The Daily Trip Tracking page: everything it calls is a read (the
    # route-static POST counts as "view", see DailyTripCollectionPointViewSet).
    ("schedule-operations", "daily-trip-tracking"): {
        "lookups": (
            "schedule-operations/daily-trip-collection-points",
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/route-detour-waypoints",
            "schedule-setup/staff-templates",
            "schedule-setup/alternative-staff-templates",
            "masters/plants",
        ),
    },
    # Detours are drawn and saved from the static route map itself, on a
    # trip plan's route or as day-only detours on one daily trip.
    ("schedule-operations", "static-route-map"): {
        "includes": (
            "schedule-operations/route-detour-waypoints",
            "schedule-operations/trip-plan-static-routes",
        ),
        "lookups": (
            "schedule-setup/trip-plans",
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/daily-trip-collection-points",
        ),
    },
    ("schedule-operations", "daily-trip-household-collections"): {
        "lookups": ("customer-masters/customercreations",),
    },
    ("schedule-operations", "bin-collection-events"): {
        "lookups": (
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/daily-trip-collection-points",
        ),
    },
    ("schedule-operations", "daily-trip-logs"): {
        "lookups": (
            "schedule-operations/daily-trip-household-collections",
            "waste-types/wastetypes",
        ),
    },
    ("schedule-operations", "wastecollections"): {
        "lookups": (
            "customer-masters/customercreations",
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/daily-trip-household-collections",
        ),
    },
    ("schedule-operations", "vehicle-breakdowns"): {
        "lookups": ("schedule-operations/daily-trip-assignments",),
    },

    # ---------------- complaints ----------------
    ("complaint-ticket", "tickets"): {
        "lookups": (
            "complaint-ticket/categories",
            "complaint-ticket/subcategories",
            "complaint-ticket/priorities",
            "complaint-ticket/sources",
            "complaint-ticket/statuses",
            "complaint-ticket/feedback",
        ),
    },
    # The Complaint Types page is backed by these three screens (its tabs).
    ("complaint-masters", "types"): {"lookups": _COMPLAINT_MASTER_LOOKUPS},
    ("complaint-masters", "categories"): {"lookups": _COMPLAINT_MASTER_LOOKUPS},
    ("complaint-masters", "subcategories"): {"lookups": _COMPLAINT_MASTER_LOOKUPS},
    ("complaint-masters", "sla-rules"): {"lookups": _COMPLAINT_MASTER_LOOKUPS},

    # ---------------- reports ----------------
    ("reports", "daily-waste-comparisons"): {
        "lookups": ("masters/panchayat", "masters/zones"),
    },
    ("reports", "monthly-waste-comparison"): {
        "lookups": ("masters/panchayat", "masters/zones"),
    },
    ("reports", "complaints-report"): {
        "lookups": ("masters/zones", "masters/wards"),
    },
}


# Screens shown together under one heading in the permission forms, and the
# sidebar's name for each module/screen, both come from the one catalog
# (app/utils/permission_catalog.py). Each grouped screen keeps its own grant
# rows; ticking the heading ticks every screen in the group.
SCREEN_GROUPS = _catalog.SCREEN_GROUPS
MAINSCREEN_LABELS = _catalog.MAINSCREEN_LABELS
SCREEN_LABELS = _catalog.SCREEN_LABELS
SCREEN_GROUP_OF = {
    screen: key for key, group in SCREEN_GROUPS.items() for screen in group["screens"]
}


def screen_group(userscreen_name):
    """(group key, group label) for a screen, or (None, None)."""
    key = SCREEN_GROUP_OF.get(userscreen_name)
    return (key, SCREEN_GROUPS[key]["label"]) if key else (None, None)


def mainscreen_label(mainscreen_name):
    """Sidebar label for a main screen, falling back to its catalog name."""
    return MAINSCREEN_LABELS.get(mainscreen_name, mainscreen_name)


def screen_label(userscreen_name):
    """Sidebar label for a user screen, falling back to its catalog name."""
    return SCREEN_LABELS.get(userscreen_name, userscreen_name)


def _index(kind):
    index = {}
    for owner, deps in SCREEN_DEPENDENCIES.items():
        for resource in deps.get(kind, ()):
            index.setdefault(resource, []).append(owner)
    return index


# "<url-module>/<route>" -> [(mainscreen, userscreen), ...] owning it.
INCLUDED_BY = _index("includes")
LOOKUP_FOR = _index("lookups")
