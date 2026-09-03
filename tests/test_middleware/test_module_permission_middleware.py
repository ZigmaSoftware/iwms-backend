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
