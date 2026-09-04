"""Guards on the mobile permission wiring.

There is ONE permission list: a screen ticked on an access configuration
governs the web screen and the mobile screen alike. Two things can silently
drift out of step with that, and both have already caused a production 403 that
looked like a broken screen:

  * a screen named in a role template or a visibility rule that no longer
    exists — the lookup returns nothing and the app is denied, with no error
    anywhere to say why (the `user-creations` -> `staff-creations` rename did
    exactly this to the driver template);
  * an app module whose surface the app does not route to.

These tests fail in CI instead.
"""

from functools import lru_cache

import pytest

from app.middleware.module_permission_middleware import (
    MODULE_PERMISSION_ALIASES,
    MODULE_RESOURCE_ALLOWLIST,
    ModulePermissionMiddleware,
    RESOURCE_PERMISSION_ALIASES,
    _module_from_path,
    _permission_action_for_request,
    _permission_resource_for_request,
)
from app.serializers.operator_mobile.trip_today_serializer import MyTripTodaySerializer
from app.utils.app_feature_grants import (
    APP_MODULE_CHOICES,
    APP_MODULE_SEED,
    APP_SURFACE_CONFIG,
    APP_SURFACE_KEYS,
    CITIZEN_APP_SCREENS,
    ROLE_SCREEN_TEMPLATES,
    SCREEN_PERMISSIONS,
    visible_screens,
)
from app.utils.permission_response import apply_role_defaults, fallback_app_module

VALID_ACTIONS = {"view", "add", "edit", "delete", "use"}


@lru_cache(maxsize=1)
def _registered_routes():
    """Every (module, resource) -> viewset the router actually serves."""
    from app.urls.base_urls import router

    routes = {}
    for group, entries in router.group_map.items():
        for entry in entries:
            resource = str(entry.get("prefix") or "").split("/")[-1]
            if resource:
                routes[(group, resource)] = entry.get("viewset")
    return routes


def _resource_is_reachable(module, resource):
    """Replays the middleware's own allowlist check.

    A grant is reachable when the route exists AND the middleware would accept
    it — which it decides from the URL segment *or* the viewset's
    `permission_resource` (defaulting to the class name minus "ViewSet"), so
    both are tried, exactly as `process_view` does.
    """
    normalize = ModulePermissionMiddleware._normalize_permission_key

    url_modules = {module}
    for url_module, alias in MODULE_PERMISSION_ALIASES.items():
        if alias == module:
            url_modules.add(url_module)

    routes = _registered_routes()
    for url_module in url_modules:
        viewset = routes.get((url_module, resource))
        if viewset is None:
            continue

        permission_resource = getattr(
            viewset, "permission_resource", viewset.__name__.replace("ViewSet", "")
        )
        candidates = {resource, permission_resource}
        candidates.update(RESOURCE_PERMISSION_ALIASES.get(permission_resource, ()))

        allowed = {
            normalize(name)
            for name in MODULE_RESOURCE_ALLOWLIST.get(url_module, set())
        }
        if any(normalize(c) in allowed for c in candidates if c):
            return True
    return False


# ============================================================
# APP MODULE MASTER
# ============================================================

def test_every_app_module_has_a_surface_and_route():
    for entry in APP_MODULE_SEED:
        assert entry["module_key"].startswith("app-")
        assert entry["surface_key"]
        assert entry["route"].startswith("/")
        assert entry["label"]


def test_app_module_keys_and_surfaces_are_unique():
    keys = [e["module_key"] for e in APP_MODULE_SEED]
    surfaces = [e["surface_key"] for e in APP_MODULE_SEED]
    assert len(keys) == len(set(keys))
    assert len(surfaces) == len(set(surfaces))


def test_app_module_choices_cover_every_module_plus_none():
    values = {value for value, _ in APP_MODULE_CHOICES}
    assert values == set(APP_SURFACE_KEYS) | {"none"}


def test_surface_config_matches_the_master():
    assert set(APP_SURFACE_CONFIG) == set(APP_SURFACE_KEYS)


def test_operator_mobile_routes_are_protected_by_daily_operations_permissions():
    assert _module_from_path("/api/v1/operator-mobile/my-trips-today/") == "operator-mobile"
    assert MODULE_PERMISSION_ALIASES["operator-mobile"] == "schedule-operations"


@pytest.mark.parametrize(
    ("resource", "expected_permission_resource"),
    [
        ("my-trip-today", "DailyTripAssignment"),
        ("my-trips-today", "DailyTripAssignment"),
        ("trip-history", "DailyTripAssignment"),
        ("validate-bin-qr", "DailyTripCollectionPoint"),
        ("scan-bin", "BinCollectionEvent"),
        ("trip-lifecycle", "DailyTripAssignment"),
    ],
)
def test_operator_mobile_resources_are_reachable(resource, expected_permission_resource):
    assert _resource_is_reachable("operator-mobile", resource)
    viewset = _registered_routes()[("operator-mobile", resource)]
    assert getattr(viewset, "permission_resource") == expected_permission_resource


def test_operator_mobile_permission_resources_resolve_to_seeded_screen_keys():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "daily-trip-assignments": ["view", "edit"],
        "daily-trip-collection-points": ["view", "edit"],
        "daily-trip-household-collections": ["view", "edit"],
        "bin-collection-events": ["view", "add"],
    }

    assert middleware._resolve_allowed_actions(
        permissions,
        "DailyTripAssignment",
        "my-trips-today",
    ) == ["view", "edit"]
    assert middleware._resolve_allowed_actions(
        permissions,
        "DailyTripCollectionPoint",
        "validate-bin-qr",
    ) == ["view", "edit"]
    assert middleware._resolve_allowed_actions(
        permissions,
        "DailyTripHouseholdCollection",
        "trip-stops",
    ) == ["view", "edit"]
    assert middleware._resolve_allowed_actions(
        permissions,
        "BinCollectionEvent",
        "scan-bin",
    ) == ["view", "add"]


def test_trip_today_serializer_reads_middleware_resolved_permissions():
    class Request:
        resolved_permissions = {
            "schedule-operations": {
                "daily-trip-collection-points": ["view"],
            },
        }

    serializer = MyTripTodaySerializer(context={"request": Request()})

    assert serializer._has_screen_permission(
        "schedule-operations",
        "daily-trip-collection-points",
    )
    assert not serializer._has_screen_permission(
        "schedule-operations",
        "daily-trip-household-collections",
    )


def test_attendance_routes_are_protected_by_attendance_permission():
    assert _module_from_path("/api/v1/attendance/daily-attendance/today/") == "attendance"
    assert _resource_is_reachable("attendance", "daily-attendance")
    assert _resource_is_reachable("attendance", "staff-profile")
    assert _resource_is_reachable("attendance", "register")
    assert _resource_is_reachable("attendance", "recognize")


def test_attendance_permission_resources_resolve_to_seeded_screen_key():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {"attendance": ["view", "add", "edit"]}

    assert middleware._resolve_allowed_actions(
        permissions,
        "AttendanceList",
        "daily-attendance",
    ) == permissions["attendance"]
    assert middleware._resolve_allowed_actions(
        permissions,
        "StaffProfile",
        "staff-profile",
    ) == permissions["attendance"]
    assert middleware._resolve_allowed_actions(
        permissions,
        "Register",
        "register",
    ) == permissions["attendance"]
    assert middleware._resolve_allowed_actions(
        permissions,
        "Recognize",
        "recognize",
    ) == permissions["attendance"]


def test_operator_mobile_household_stops_use_household_collection_permission():
    class Request:
        query_params = {"type": "household"}

    viewset = _registered_routes()[("operator-mobile", "trip-stops")]
    resource = _permission_resource_for_request(
        viewset,
        Request(),
        getattr(viewset, "permission_resource"),
    )
    assert resource == "DailyTripHouseholdCollection"


def test_operator_mobile_post_actions_match_the_real_write_permission():
    class Request:
        query_params = {}

    lifecycle = _registered_routes()[("operator-mobile", "trip-lifecycle")]
    validate_qr = _registered_routes()[("operator-mobile", "validate-bin-qr")]
    scan_bin = _registered_routes()[("operator-mobile", "scan-bin")]

    assert _permission_action_for_request(lifecycle, Request(), "add") == "edit"
    assert _permission_action_for_request(validate_qr, Request(), "add") == "view"
    assert _permission_action_for_request(scan_bin, Request(), "add") == "add"


# ============================================================
# SCREEN VISIBILITY
# ============================================================

@pytest.mark.parametrize("screen_key", sorted(SCREEN_PERMISSIONS))
def test_visibility_rules_name_reachable_permissions(screen_key):
    requirement = SCREEN_PERMISSIONS[screen_key]
    if requirement is None:
        return

    module, resource, action = requirement
    assert action in VALID_ACTIONS, f"{screen_key}: unknown action '{action}'"
    assert _resource_is_reachable(module, resource), (
        f"{screen_key} is gated on '{module}/{resource}', which the middleware "
        "would never match — the screen would be permanently hidden"
    )


def test_every_screen_key_belongs_to_a_real_surface():
    for screen_key in SCREEN_PERMISSIONS:
        surface = screen_key.split(".", 1)[0]
        assert surface in APP_SURFACE_KEYS, (
            f"'{screen_key}' names surface '{surface}', which is not an app module"
        )


def test_a_screen_appears_when_its_permission_is_granted():
    permissions = {"schedule-operations": {"daily-trip-assignments": ["view"]}}
    visible = visible_screens(permissions, "supervisor")
    assert "supervisor.trips" in visible
    assert "supervisor.dashboard" in visible


def test_a_screen_is_hidden_when_its_permission_is_missing():
    permissions = {"schedule-operations": {"daily-trip-assignments": ["view"]}}
    visible = visible_screens(permissions, "supervisor")
    assert "supervisor.complaints" not in visible
    assert "supervisor.crew" not in visible


def test_profiles_with_no_permission_are_still_visible_but_attendance_is_not():
    """Profile is the user's own self-service screen. Attendance is a strict
    operational feature and must be granted explicitly."""
    visible = visible_screens({}, "supervisor")
    assert "supervisor.profile" in visible
    assert "supervisor.attendance" not in visible


def test_partial_grants_do_not_hide_a_screen():
    """A screen is gated on its main list permission only. Gating on every
    endpoint it reads would mean one missed tick makes a tab vanish."""
    permissions = {"schedule-operations": {"daily-trip-assignments": ["view"]}}
    # Trips also reads trip-plans and vehicle-creation, neither granted here.
    assert "supervisor.trips" in visible_screens(permissions, "supervisor")


def test_module_alias_is_honoured_in_visibility():
    """`customers` is the permission name for the `customer-masters` routes."""
    permissions = {"customers": {"customercreations": ["view"]}}
    assert "supervisor.households" in visible_screens(permissions, "supervisor")


def test_citizen_screens_are_ticked_explicitly():
    granted = visible_screens({}, "citizen", citizen_screens={"app-citizen-complaints"})
    assert granted == ["citizen.complaints"]

    none_granted = visible_screens({}, "citizen", citizen_screens=set())
    assert none_granted == []


def test_citizen_screen_names_match_the_seeded_screens():
    for screen_key in SCREEN_PERMISSIONS:
        if not screen_key.startswith("citizen."):
            continue
        name = f"app-citizen-{screen_key.split('.', 1)[1]}"
        assert name in CITIZEN_APP_SCREENS, f"{screen_key} has no seeded screen"


def test_role_template_is_a_non_destructive_compatibility_floor():
    permissions = {"masters": {"districts": ["add"]}}
    merged = apply_role_defaults(permissions, "Company Supervisor")

    assert merged["masters"]["districts"] == ["add"]
    assert "view" in merged["schedule-operations"]["daily-trip-assignments"]
    assert "add" in merged["schedule-operations"]["retrip-requests"]
    assert "add" in merged["complaint-ticket"]["tickets"]


def test_role_template_can_supply_legacy_app_module():
    assert fallback_app_module("Company Supervisor", None) == "supervisor"
    assert fallback_app_module("Company Driver", "driver") == "driver"
    assert fallback_app_module("Company Supervisor", "none") == "supervisor"


# ============================================================
# ROLE TEMPLATES
# ============================================================

@pytest.mark.parametrize("role", sorted(ROLE_SCREEN_TEMPLATES))
def test_role_templates_name_reachable_screens(role):
    for module, screens in ROLE_SCREEN_TEMPLATES[role].items():
        for resource, actions in screens.items():
            lookup = module if module in MODULE_RESOURCE_ALLOWLIST else None
            if lookup is None:
                lookup = next(
                    (
                        url_module
                        for url_module, alias in MODULE_PERMISSION_ALIASES.items()
                        if alias == module and url_module in MODULE_RESOURCE_ALLOWLIST
                    ),
                    None,
                )
            assert lookup, f"{role}: module '{module}' does not exist"
            assert _resource_is_reachable(lookup, resource), (
                f"{role}: '{module}/{resource}' is not reachable — backfilling "
                "this template would grant nothing"
            )
            unknown = set(actions) - VALID_ACTIONS
            assert not unknown, f"{role}: unknown actions {unknown}"


@pytest.mark.parametrize("role", ["driver", "operator", "supervisor"])
def test_role_template_covers_every_screen_that_role_can_see(role):
    """Backfilling a role must actually unhide that role's screens.

    Otherwise the backfill runs, reports success, and the user still opens an
    app with no tabs in it.
    """
    template = ROLE_SCREEN_TEMPLATES[role]
    permissions = {
        module: {screen: list(actions) for screen, actions in screens.items()}
        for module, screens in template.items()
    }
    visible = visible_screens(permissions, role)

    expected = [key for key in SCREEN_PERMISSIONS if key.startswith(f"{role}.")]
    missing = sorted(set(expected) - set(visible))
    assert not missing, (
        f"{role}: backfill would leave these screens hidden: {missing}"
    )
