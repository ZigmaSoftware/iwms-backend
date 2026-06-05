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


def test_department_master_permission_matches_departments_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "department-masters": ["add", "delete", "edit", "show", "view"],
    }

    assert _resource_is_allowed("masters", "Department", "departments")
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

    assert _resource_is_allowed("masters", "Designation", "designations")
    assert middleware._resolve_allowed_actions(
        permissions,
        "Designation",
        "designations",
    ) == ["add", "delete", "edit", "show", "view"]
