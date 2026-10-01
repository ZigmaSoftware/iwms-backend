"""The permission catalog keeps the seeder, the middleware and the frontend
sidebar on the same names. These tests fail when any of them drifts."""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.test import RequestFactory

import app.middleware.module_permission_middleware as mw
from app.utils import permission_catalog as catalog
from app.utils.permission_catalog_export import FRONTEND_CATALOG_PATH, render_typescript
from app.utils.screen_dependencies import INCLUDED_BY, LOOKUP_FOR, SCREEN_DEPENDENCIES

SIDEBAR = (
    Path(__file__).resolve().parents[3]
    / "iwms-frontend/src/layouts/admin/components/AppSidebar.tsx"
)


def _routes():
    """{"<url-module>/<route>": viewset} for every router registration."""
    from app.urls.base_urls import router

    return {
        f"{group}/{entry['prefix']}": entry["viewset"]
        for group, entries in router.group_map.items()
        for entry in entries
    }


def _uses_request_hook(viewset):
    return callable(getattr(viewset, "permission_resource_for_request", None))


# ---------------------------------------------------------------- structure

def test_screen_names_are_unique_across_modules():
    names = [n for screens in catalog.SCREEN_STRUCTURE.values() for n in screens]
    assert len(names) == len(set(names))


def test_every_screen_group_has_a_label_and_screens():
    used = {s["group"] for m in catalog.MODULES.values() for s in m["screens"]} - {None}
    assert used == set(catalog.GROUP_LABELS)


def test_screen_dependencies_name_catalog_screens_and_real_routes():
    routes = _routes()
    for (module, screen), deps in SCREEN_DEPENDENCIES.items():
        assert screen in catalog.SCREEN_STRUCTURE.get(module, ()), (module, screen)
        for route in (*deps.get("includes", ()), *deps.get("lookups", ())):
            assert route in routes, f"{(module, screen)} depends on unknown route {route}"


# ---------------------------------------------------------------- middleware

def test_every_catalog_route_is_registered():
    routes = _routes()
    missing = sorted(r for r in catalog.ROUTE_OWNERS if r not in routes)
    assert not missing, f"catalog routes with no router registration: {missing}"


def test_every_protected_route_has_a_known_owner():
    """A protected route must be owned by a screen, reached through a screen's
    dependencies, resolved per request, or deliberately superadmin-only."""
    unowned = sorted(
        route
        for route, viewset in _routes().items()
        if route.split("/")[0] in mw.PROTECTED_MODULES
        and route not in catalog.ROUTE_OWNERS
        and route not in INCLUDED_BY
        and route not in LOOKUP_FOR
        and route not in catalog.SUPERADMIN_ONLY_ROUTES
        and route not in catalog.AUTH_ONLY_ROUTES
        and not _uses_request_hook(viewset)
    )
    assert not unowned, (
        "Protected routes no screen can grant — add them to a screen's "
        f"`routes` in app/utils/permission_catalog.py: {unowned}"
    )


def _request(monkeypatch, route, viewset, permissions, method="get"):
    def authenticate(request):
        request.user = SimpleNamespace(is_superuser=False)
        return None

    monkeypatch.setattr(mw, "_authenticate_request", authenticate)
    monkeypatch.setattr(mw, "_resolve_permissions_for_request", lambda r: permissions)

    def view(request):
        return None

    view.cls = viewset
    request = getattr(RequestFactory(), method)(f"/api/v1/{route}/")
    return mw.ModulePermissionMiddleware(lambda r: None).process_view(request, view, (), {})


@pytest.mark.parametrize("route", sorted(catalog.ROUTE_OWNERS))
def test_owner_grant_authorizes_its_routes(monkeypatch, route):
    viewset = _routes()[route]
    if _uses_request_hook(viewset):
        pytest.skip("resource chosen per request")
    module, screen = catalog.ROUTE_OWNERS[route]

    # All four actions: some routes map a GET to another action (e.g.
    # operator-mobile/trip-lifecycle reads as "edit").
    grant = {module: {screen: ["view", "add", "edit", "delete"]}}
    granted = _request(monkeypatch, route, viewset, grant)
    assert granted is None, f"{module}/{screen} should open {route}: {granted.content}"

    denied = _request(monkeypatch, route, viewset, {})
    assert denied is not None and denied.status_code == 403


def test_column_permissions_follow_the_companywise_permission_screen(monkeypatch):
    route = "screen-managements/column-permissions"
    perms = {"screen-managements": {"companywisescreenpermissions": ["view", "edit"]}}
    assert _request(monkeypatch, route, _routes()[route], perms, "patch") is None


def test_attendance_page_records_follow_the_attendance_screen(monkeypatch):
    route = "attendance/external-records"
    perms = {"attendance": {"attendance": ["view"]}}
    assert _request(monkeypatch, route, _routes()[route], perms) is None


# ---------------------------------------------------------------- frontend

def test_generated_frontend_catalog_is_up_to_date():
    if not FRONTEND_CATALOG_PATH.parent.parent.exists():
        pytest.skip("frontend checkout not present")
    assert FRONTEND_CATALOG_PATH.exists() and (
        FRONTEND_CATALOG_PATH.read_text() == render_typescript()
    ), "Run: python manage.py sync_permission_catalog"


def test_sidebar_names_permissions_only_through_the_catalog():
    if not SIDEBAR.exists():
        pytest.skip("frontend checkout not present")
    source = SIDEBAR.read_text()

    raw = [m for m in re.findall(r'\bmodule: "([^"]+)"', source) if m != "dashboard"]
    assert not raw, f"use permissionFor(...) instead of raw module names: {raw}"

    calls = re.findall(r'permissionFor\(([^)]*)\)', source)
    assert calls, "no permissionFor(...) calls found in AppSidebar.tsx"
    for call in calls:
        names = re.findall(r'"([^"]+)"', call)
        if not names:  # the mention in a comment
            continue
        module, *screens = names
        for name in screens:
            assert name in catalog.SCREEN_STRUCTURE.get(module, ()), (module, name)
