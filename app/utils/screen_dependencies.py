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
module_permission_middleware.py); `superadmin/*`, `reports/*` and the other
unprotected groups are reachable by any authenticated user already.
"""

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
    # Also gates the Daily Trip Tracking page in the sidebar.
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
    # Detours are drawn and saved from the static route map itself.
    ("schedule-operations", "static-route-map"): {
        "includes": ("schedule-operations/route-detour-waypoints",),
        "lookups": (
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
    ("schedule-masters", "daily-waste-comparisons"): {
        "lookups": ("masters/panchayat", "masters/zones"),
    },
    ("schedule-masters", "monthly-waste-comparison"): {
        "lookups": ("masters/panchayat", "masters/zones"),
    },
}


# Screens shown together under one heading in the permission forms. Each
# screen keeps its own grant rows and can still be ticked on its own; ticking
# an action on the heading ticks it on every screen in the group.
# Keyed by a stable group key; screens are userscreen_names.
SCREEN_GROUPS = {
    "daily-trip-plan": {
        "label": "Daily Trip Plan",
        "screens": (
            "daily-trip-assignments",
            "daily-trip-collection-points",
            "daily-trip-household-collections",
        ),
    },
    "staff-user-type": {
        "label": "Staff User Type",
        "screens": (
            "staffusertypes",
            "contractorusertypes",
        ),
    },
}
SCREEN_GROUP_OF = {
    screen: key for key, group in SCREEN_GROUPS.items() for screen in group["screens"]
}


def screen_group(userscreen_name):
    """(group key, group label) for a screen, or (None, None)."""
    key = SCREEN_GROUP_OF.get(userscreen_name)
    return (key, SCREEN_GROUPS[key]["label"]) if key else (None, None)


def _index(kind):
    index = {}
    for owner, deps in SCREEN_DEPENDENCIES.items():
        for resource in deps.get(kind, ()):
            index.setdefault(resource, []).append(owner)
    return index


# "<url-module>/<route>" -> [(mainscreen, userscreen), ...] owning it.
INCLUDED_BY = _index("includes")
LOOKUP_FOR = _index("lookups")
