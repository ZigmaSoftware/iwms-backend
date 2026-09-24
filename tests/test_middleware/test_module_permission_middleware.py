from app.middleware.module_permission_middleware import (
    MODULE_RESOURCE_ALLOWLIST,
    ModulePermissionMiddleware,
    _resource_allowlist_candidates,
)


def _resource_is_allowed(module, permission_resource, route_resource):
    allowed_resource_keys = {
        ModulePermissionMiddleware._normalize_permission_key(resource)
        for resource in MODULE_RESOURCE_ALLOWLIST[module]
    }
    resource_candidates = _resource_allowlist_candidates(
        permission_resource,
        route_resource,
    )
    return any(
        ModulePermissionMiddleware._normalize_permission_key(candidate)
        in allowed_resource_keys
        for candidate in resource_candidates
    )


def test_nested_register_fcm_token_routes_are_auth_only(monkeypatch):
    from django.test import RequestFactory
    import app.middleware.module_permission_middleware as middleware_module

    sentinel = object()
    seen_paths = []

    def fake_authenticate_request(request):
        seen_paths.append(request.path)
        return sentinel

    monkeypatch.setattr(
        middleware_module,
        "_authenticate_request",
        fake_authenticate_request,
    )
    middleware = ModulePermissionMiddleware(lambda request: None)
    factory = RequestFactory()

    for path in (
        "/api/v1/staff-creations/staffcreation/register-fcm-token/",
        "/api/v1/customer-masters/customercreations/register-fcm-token/",
    ):
        request = factory.post(
            path,
            {"fcm_token": "TEST-TOKEN"},
            content_type="application/json",
        )

        result = middleware.process_view(request, lambda request: None, (), {})
        assert result is sentinel

    assert seen_paths == [
        "/api/v1/staff-creations/staffcreation/register-fcm-token/",
        "/api/v1/customer-masters/customercreations/register-fcm-token/",
    ]


def test_department_master_permission_matches_departments_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "department-masters": ["add", "delete", "edit", "show", "view"],
    }

    assert _resource_is_allowed("staff-creations", "Department", "departments")
    assert middleware._resolve_allowed_actions(
        permissions,
        "Department",
        "departments",
    ) == ["add", "delete", "edit", "show", "view"]


def test_designation_master_permission_matches_designations_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "designation-masters": ["add", "delete", "edit", "show", "view"],
    }

    assert _resource_is_allowed("staff-creations", "Designation", "designations")
    assert middleware._resolve_allowed_actions(
        permissions,
        "Designation",
        "designations",
    ) == ["add", "delete", "edit", "show", "view"]


def test_contractor_usertype_permission_matches_contractorusertypes_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "contractorusertypes": ["view", "add", "edit", "delete"],
    }

    assert _resource_is_allowed("role-assigns", "ContractorUserType", "contractorusertypes")
    assert middleware._resolve_allowed_actions(
        permissions,
        "ContractorUserType",
        "contractorusertypes",
    ) == ["view", "add", "edit", "delete"]


def test_staff_template_creation_permission_matches_staff_templates_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "staff-templates": ["view", "add", "edit", "delete"],
    }

    assert _resource_is_allowed(
        "schedule-masters",
        "StaffTemplateCreation",
        "staff-templates",
    )
    assert middleware._resolve_allowed_actions(
        permissions,
        "StaffTemplateCreation",
        "staff-templates",
    ) == ["view", "add", "edit", "delete"]


def test_staff_access_configuration_permission_matches_hyphenated_screen_name():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "staff-access-configuration": ["view", "add", "edit", "delete"],
    }

    assert _resource_is_allowed(
        "staff-creations",
        "staffaccessconfiguration",
        "staff-access-configuration",
    )
    assert middleware._resolve_allowed_actions(
        permissions,
        "staffaccessconfiguration",
        "staff-access-configuration",
    ) == ["view", "add", "edit", "delete"]


def test_permission_resource_for_request_hook_gets_raw_wsgi_request():
    """`process_view` calls a viewset's `permission_resource_for_request`
    hook with the raw `WSGIRequest`, before DRF wraps it into its own
    `Request` — so a hook reading query params must use `request.GET`, not
    `request.query_params` (that attribute doesn't exist yet at this point).

    `TripStopsViewSet` used `.query_params` and 500'd on every single call to
    `/api/v1/operator-mobile/trip-stops/` as a result — this pins the fix and
    guards the contract for the next resolver hook written against it.
    """
    from django.test import RequestFactory

    from app.middleware.module_permission_middleware import (
        _permission_resource_for_request,
    )
    from app.viewsets.operator_mobile.trip_stops_viewset import (
        TripStopsViewSet,
    )

    factory = RequestFactory()

    household_request = factory.get(
        "/api/v1/operator-mobile/trip-stops/",
        {"assignment_id": "TRIP-1", "type": "household", "page": "2"},
    )
    assert not hasattr(household_request, "query_params")
    assert (
        _permission_resource_for_request(
            TripStopsViewSet, household_request, "DailyTripCollectionPoint"
        )
        == "DailyTripHouseholdCollection"
    )

    bin_request = factory.get(
        "/api/v1/operator-mobile/trip-stops/",
        {"assignment_id": "TRIP-1", "type": "bin"},
    )
    assert (
        _permission_resource_for_request(
            TripStopsViewSet, bin_request, "DailyTripCollectionPoint"
        )
        == "DailyTripCollectionPoint"
    )

    no_type_request = factory.get(
        "/api/v1/operator-mobile/trip-stops/", {"assignment_id": "TRIP-1"}
    )
    assert (
        _permission_resource_for_request(
            TripStopsViewSet, no_type_request, "DailyTripCollectionPoint"
        )
        == "DailyTripCollectionPoint"
    )


def test_attendance_face_config_is_auth_only(monkeypatch):
    """Regression test for a two-stage bug on this exact endpoint.

    Attempt 1 added "face-config/" to AUTH_ONLY_SUFFIXES, which only matches
    a BARE `/api/v1/face-config/` via string concatenation — never the nested
    `attendance/face-config/` this project actually serves — so it silently
    did nothing (the same class of bug the register-fcm-token comment above
    already documents).

    Attempt 2 added "FaceConfig" to MODULE_RESOURCE_ALLOWLIST["attendance"],
    which passed the *resource* check but still 403'd every request: the
    subsequent *action* check resolves `allowed_actions` from a staff
    member's granted `StaffAccessConfigurationPermission` rows, which only
    ever exist for a seeded `UserScreen` — and "face-config" was never seeded
    as one (there is nothing for an admin to tick in Staff Access
    Configuration, because this isn't a business screen). So
    `allowed_actions` was permanently empty for every staff member
    regardless of role, and the endpoint could never be granted at all.

    The actual fix routes it through a dedicated `endswith` bypass, exactly
    like `register-fcm-token/` above: authenticate, then skip the whole
    module/resource/action pipeline. This asserts that happens — the mocked
    `_authenticate_request` result is returned directly, proving neither the
    resource allowlist nor the permission catalog is consulted at all.
    """
    import app.middleware.module_permission_middleware as middleware_module
    from django.test import RequestFactory

    sentinel = object()
    monkeypatch.setattr(
        middleware_module, "_authenticate_request", lambda request: sentinel
    )

    middleware = ModulePermissionMiddleware(lambda request: None)
    request = RequestFactory().get("/api/v1/attendance/face-config/")

    result = middleware.process_view(request, lambda request: None, (), {})
    assert result is sentinel


def test_face_config_is_not_in_the_attendance_permission_catalog():
    """Companion to the bypass test above: "face-config"/"FaceConfig" must
    NOT be re-added to the granular allowlist. Doing so would look like a
    real fix but cannot work — see the long comment on the reason above —
    and having two different mechanisms both claiming to authorize the same
    endpoint is exactly what made the real gate hard to find the first time.
    """
    assert not _resource_is_allowed("attendance", "FaceConfig", "face-config")


def test_register_and_recognize_remain_allowed():
    """Guards against the fix above accidentally narrowing the existing
    grants it was added alongside."""
    assert _resource_is_allowed("attendance", "Register", "register")
    assert _resource_is_allowed("attendance", "Recognize", "recognize")


# ------------------------------------------------------------------
# Screen dependencies: one grant on a page's own screen covers the other
# APIs that page calls (app/utils/screen_dependencies.py).
# ------------------------------------------------------------------

def _run_as(monkeypatch, permissions, method, path, view_class):
    from types import SimpleNamespace
    from django.test import RequestFactory
    import app.middleware.module_permission_middleware as middleware_module

    def fake_authenticate_request(request):
        request.user = SimpleNamespace(is_superuser=False)
        return None

    monkeypatch.setattr(middleware_module, "_authenticate_request", fake_authenticate_request)
    monkeypatch.setattr(
        middleware_module, "_resolve_permissions_for_request", lambda request: permissions
    )
    request = getattr(RequestFactory(), method)(path)
    view_func = SimpleNamespace(cls=view_class)
    result = ModulePermissionMiddleware(lambda r: None).process_view(request, view_func, (), {})
    return 200 if result is None else result.status_code, request


def _view(resource):
    return type(f"{resource}ViewSet", (), {"permission_resource": resource})


ASSIGNMENT_EDITOR = {
    "schedule-operations": {"daily-trip-assignments": ["view", "edit"]},
}


def test_assignment_grant_does_not_cover_stop_screens(monkeypatch):
    # The stops are separate screens in the "Daily Trip Plan" group: an admin
    # who unticks one must actually take that access away.
    for resource, route in (
        ("DailyTripHouseholdCollection", "daily-trip-household-collections"),
        ("DailyTripCollectionPoint", "daily-trip-collection-points"),
    ):
        status, _ = _run_as(
            monkeypatch, ASSIGNMENT_EDITOR, "patch",
            f"/api/v1/schedule-operations/{route}/X1/", _view(resource),
        )
        assert status == 403


def test_lookup_grant_is_read_only(monkeypatch):
    status, request = _run_as(
        monkeypatch, ASSIGNMENT_EDITOR, "get",
        "/api/v1/waste-types/bins/", _view("Bin"),
    )
    assert status == 200
    assert request.permission_use_only is True

    status, _ = _run_as(
        monkeypatch, ASSIGNMENT_EDITOR, "post",
        "/api/v1/waste-types/bins/", _view("Bin"),
    )
    assert status == 403


def test_lookup_needs_a_grant_on_an_owning_screen(monkeypatch):
    status, _ = _run_as(
        monkeypatch, {"masters": {"districts": ["view"]}}, "get",
        "/api/v1/waste-types/bins/", _view("Bin"),
    )
    assert status == 403


def test_owner_grant_under_legacy_module_name_still_counts(monkeypatch):
    status, _ = _run_as(
        monkeypatch,
        {"schedule-masters": {"daily-trip-assignments": ["view"]}},
        "get",
        "/api/v1/customer-masters/customercreations/",
        _view("CustomerCreation"),
    )
    assert status == 200


def test_ward_form_dropdowns_come_with_the_ward_screen(monkeypatch):
    perms = {"masters": {"wards": ["view", "add"]}}
    for path, resource in (
        ("/api/v1/common-masters/states/", "State"),
        ("/api/v1/masters/districts/", "District"),
        ("/api/v1/masters/zones/", "Zone"),
    ):
        status, _ = _run_as(monkeypatch, perms, "get", path, _view(resource))
        assert status == 200, path


def test_contractor_user_types_follow_their_own_grant(monkeypatch):
    # Shown under the "Staff User Type" row, but saved as its own screen, so
    # a staff-user-type grant alone does not reach it.
    status, _ = _run_as(
        monkeypatch,
        {"role-assigns": {"staffusertypes": ["view", "add", "edit"]}},
        "post",
        "/api/v1/role-assigns/contractorusertypes/",
        _view("ContractorUserType"),
    )
    assert status == 403

    status, _ = _run_as(
        monkeypatch,
        {"role-assigns": {"contractorusertypes": ["add"]}},
        "post",
        "/api/v1/role-assigns/contractorusertypes/",
        _view("ContractorUserType"),
    )
    assert status == 200


def test_previously_unallowlisted_resources_are_grantable(monkeypatch):
    status, _ = _run_as(
        monkeypatch,
        {"role-assigns": {"project-staff-hierarchy": ["view"]}},
        "get",
        "/api/v1/role-assigns/project-staff-hierarchy/",
        _view("ProjectStaffHierarchy"),
    )
    assert status == 200

    status, _ = _run_as(
        monkeypatch,
        {"schedule-operations": {"static-route-map": ["view", "add", "delete"]}},
        "post",
        "/api/v1/schedule-operations/route-detour-waypoints/",
        _view("RouteDetourWaypoint"),
    )
    assert status == 200


def test_route_static_post_only_needs_view(monkeypatch):
    from app.viewsets.core_modules.daily_operations.daily_trip_collection_point_viewset import (
        DailyTripCollectionPointViewSet,
    )

    status, _ = _run_as(
        monkeypatch,
        {"schedule-operations": {"daily-trip-collection-points": ["view"]}},
        "post",
        "/api/v1/schedule-operations/daily-trip-collection-points/route-static/",
        DailyTripCollectionPointViewSet,
    )
    assert status == 200
