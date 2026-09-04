import hashlib
import json
import re

from django.utils import timezone

from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.staff_creations.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.utils.app_feature_grants import (
    APP_SURFACE_CONFIG as _APP_SURFACE_CONFIG,
    APP_SURFACE_KEYS,
    CITIZEN_APP_SCREENS,
    ROLE_SCREEN_TEMPLATES,
    SCREEN_PERMISSIONS,
    visible_screens,
)


ACTION_KEYS = ("view", "add", "edit", "delete", "use")

APP_SURFACE_CONFIG = _APP_SURFACE_CONFIG


def base_action_map():
    return {action: False for action in ACTION_KEYS}


def normalize_permission_key(value):
    text = (value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def build_action_permissions(queryset):
    permissions = {}
    for perm in queryset.order_by("order_no"):
        main_name = perm.mainscreen_id.mainscreen_name
        screen_name = perm.userscreen_id.userscreen_name
        action_name = (
            perm.userscreenaction_id.variable_name
            or perm.userscreenaction_id.action_name
            or ""
        ).lower()

        screen_map = permissions.setdefault(main_name, {})
        actions = screen_map.setdefault(screen_name, [])
        if action_name and action_name not in actions:
            actions.append(action_name)

    return permissions


def build_permission_details(action_queryset, column_queryset=None):
    details = {}
    screen_meta = {}

    for perm in action_queryset.order_by("mainscreen_id__order_no", "userscreen_id__order_no", "order_no"):
        main_name = perm.mainscreen_id.mainscreen_name
        screen_name = perm.userscreen_id.userscreen_name
        action_name = (
            perm.userscreenaction_id.variable_name
            or perm.userscreenaction_id.action_name
            or ""
        ).lower()

        screen_payload = details.setdefault(main_name, {}).setdefault(
            screen_name,
            {
                "mainScreenId": perm.mainscreen_id_id,
                "mainScreenName": main_name,
                "mainScreenKey": normalize_permission_key(main_name),
                "userScreenId": perm.userscreen_id_id,
                "screenKey": normalize_permission_key(
                    getattr(perm.userscreen_id, "folder_name", "") or screen_name
                ),
                "folderName": getattr(perm.userscreen_id, "folder_name", None),
                "orderNo": getattr(perm.userscreen_id, "order_no", None),
                "permissions": base_action_map(),
                "columns": [],
            },
        )
        screen_meta[perm.userscreen_id_id] = (main_name, screen_name)
        if action_name in screen_payload["permissions"]:
            screen_payload["permissions"][action_name] = True

    if column_queryset is None:
        column_queryset = CompanyUserScreenColumnPermission.objects.none()

    for column_permission in column_queryset.order_by("userscreen_id__order_no", "order_no"):
        screen_id = column_permission.userscreen_id_id
        if screen_id not in screen_meta:
            main_name = column_permission.userscreen_id.mainscreen_id.mainscreen_name
            screen_name = column_permission.userscreen_id.userscreen_name
            screen_meta[screen_id] = (main_name, screen_name)
            details.setdefault(main_name, {}).setdefault(
                screen_name,
                {
                    "mainScreenId": column_permission.userscreen_id.mainscreen_id_id,
                    "mainScreenName": main_name,
                    "mainScreenKey": normalize_permission_key(main_name),
                    "userScreenId": screen_id,
                    "screenKey": normalize_permission_key(
                        getattr(column_permission.userscreen_id, "folder_name", "")
                        or screen_name
                    ),
                    "folderName": getattr(column_permission.userscreen_id, "folder_name", None),
                    "orderNo": getattr(column_permission.userscreen_id, "order_no", None),
                    "permissions": base_action_map(),
                    "columns": [],
                },
            )

        main_name, screen_name = screen_meta[screen_id]
        column = column_permission.column_id
        details[main_name][screen_name]["columns"].append({
            "id": column.unique_id,
            "columnId": column.unique_id,
            "fieldName": column.field_name,
            "displayName": column.display_name,
            "dataType": column.data_type,
            "dbColumn": column.db_column,
            "canView": column_permission.can_view,
            "isRequired": column.is_required,
            "orderNo": column_permission.order_no,
        })

    return details


def build_column_permissions(column_queryset):
    grouped = {}
    flat = []

    for column_permission in column_queryset.order_by(
        "userscreen_id__mainscreen_id__order_no",
        "userscreen_id__order_no",
        "order_no",
    ):
        userscreen = column_permission.userscreen_id
        mainscreen = userscreen.mainscreen_id
        column = column_permission.column_id

        payload = {
            "uniqueId": column_permission.unique_id,
            "companyId": column_permission.company_id_id,
            "projectId": column_permission.project_id_id,
            "mainScreenId": mainscreen.unique_id,
            "mainScreenName": mainscreen.mainscreen_name,
            "mainScreenKey": normalize_permission_key(mainscreen.mainscreen_name),
            "userScreenId": userscreen.unique_id,
            "userScreenName": userscreen.userscreen_name,
            "screenKey": normalize_permission_key(userscreen.folder_name or userscreen.userscreen_name),
            "folderName": userscreen.folder_name,
            "columnId": column.unique_id,
            "fieldName": column.field_name,
            "displayName": column.display_name,
            "dataType": column.data_type,
            "dbColumn": column.db_column,
            "canView": column_permission.can_view,
            "isRequired": column.is_required,
            "orderNo": column_permission.order_no,
        }

        flat.append(payload)
        grouped.setdefault(mainscreen.mainscreen_name, {}).setdefault(
            userscreen.userscreen_name,
            [],
        ).append(payload)

    return {
        "grouped": grouped,
        "flat": flat,
    }


def build_module_access(action_queryset, column_queryset=None):
    modules = {}
    screen_lookup = {}

    for perm in action_queryset.order_by(
        "mainscreen_id__order_no",
        "userscreen_id__order_no",
        "order_no",
    ):
        mainscreen = perm.mainscreen_id
        userscreen = perm.userscreen_id
        action_name = (
            perm.userscreenaction_id.variable_name
            or perm.userscreenaction_id.action_name
            or ""
        ).lower()

        module_entry = modules.setdefault(
            mainscreen.unique_id,
            {
                "moduleId": mainscreen.unique_id,
                "moduleName": mainscreen.mainscreen_name,
                "moduleKey": normalize_permission_key(mainscreen.mainscreen_name),
                "orderNo": mainscreen.order_no,
                "screens": {},
            },
        )

        screen_entry = module_entry["screens"].setdefault(
            userscreen.unique_id,
            {
                "userScreenId": userscreen.unique_id,
                "screenName": userscreen.userscreen_name,
                "screenKey": normalize_permission_key(
                    userscreen.folder_name or userscreen.userscreen_name
                ),
                "folderName": userscreen.folder_name,
                "orderNo": userscreen.order_no,
                "permissions": base_action_map(),
                "columns": [],
            },
        )
        screen_lookup[userscreen.unique_id] = screen_entry

        if action_name in screen_entry["permissions"]:
            screen_entry["permissions"][action_name] = True

    if column_queryset is None:
        column_queryset = CompanyUserScreenColumnPermission.objects.none()

    for column_permission in column_queryset.order_by(
        "userscreen_id__mainscreen_id__order_no",
        "userscreen_id__order_no",
        "order_no",
    ):
        userscreen = column_permission.userscreen_id
        mainscreen = userscreen.mainscreen_id
        module_entry = modules.setdefault(
            mainscreen.unique_id,
            {
                "moduleId": mainscreen.unique_id,
                "moduleName": mainscreen.mainscreen_name,
                "moduleKey": normalize_permission_key(mainscreen.mainscreen_name),
                "orderNo": mainscreen.order_no,
                "screens": {},
            },
        )
        screen_entry = module_entry["screens"].setdefault(
            userscreen.unique_id,
            {
                "userScreenId": userscreen.unique_id,
                "screenName": userscreen.userscreen_name,
                "screenKey": normalize_permission_key(
                    userscreen.folder_name or userscreen.userscreen_name
                ),
                "folderName": userscreen.folder_name,
                "orderNo": userscreen.order_no,
                "permissions": base_action_map(),
                "columns": [],
            },
        )
        screen_lookup[userscreen.unique_id] = screen_entry

        column = column_permission.column_id
        screen_entry["columns"].append(
            {
                "columnId": column.unique_id,
                "fieldName": column.field_name,
                "displayName": column.display_name,
                "dbColumn": column.db_column,
                "dataType": column.data_type,
                "canView": column_permission.can_view,
                "isRequired": column.is_required,
                "orderNo": column_permission.order_no,
            }
        )

    payload = []
    for module in sorted(modules.values(), key=lambda item: item["orderNo"] or 0):
        screens = sorted(
            module["screens"].values(),
            key=lambda item: item["orderNo"] or 0,
        )
        payload.append(
            {
                "moduleId": module["moduleId"],
                "moduleName": module["moduleName"],
                "moduleKey": module["moduleKey"],
                "orderNo": module["orderNo"],
                "screens": screens,
            }
        )
    return payload


def build_fallback_module_access(permissions):
    module_access = []

    for module_name, screens in sorted((permissions or {}).items()):
        module_entry = {
            "moduleId": None,
            "moduleName": module_name,
            "moduleKey": normalize_permission_key(module_name),
            "orderNo": None,
            "screens": [],
        }

        for screen_name, action_names in sorted((screens or {}).items()):
            action_map = base_action_map()
            for action_name in action_names or []:
                normalized = normalize_permission_key(action_name)
                if normalized in action_map:
                    action_map[normalized] = True
            module_entry["screens"].append(
                {
                    "userScreenId": None,
                    "screenName": screen_name,
                    "screenKey": normalize_permission_key(screen_name),
                    "folderName": None,
                    "orderNo": None,
                    "permissions": action_map,
                    "columns": [],
                }
            )

        module_access.append(module_entry)

    return module_access


def surfaces_from_app_modules(app_modules):
    """Surfaces for the app modules ticked on an access configuration.

    This is the whole answer for the mobile app: a person may open the apps
    they were ticked for, and no others. Nothing is inferred from a role name
    or from which web screens they happen to hold, which is what used to hand
    a driver an Admin tile because someone granted them the masters screens.
    """
    ordered = []
    for surface in APP_SURFACE_KEYS:
        if surface in (app_modules or []):
            ordered.append(surface)
    return ordered


def infer_app_surfaces(
    module_access,
    permissions,
    role_name=None,
    user_type=None,
    app_module=None,
    app_modules=None,
):
    """The apps this user may open, most preferred first.

    `app_modules` are the ticked App Module surfaces; `app_module` is the
    default chosen on the creation form, used only to order them.
    """
    granted = surfaces_from_app_modules(app_modules)

    if not granted:
        # No module ticked. Web users are unaffected — they never consult this
        # for anything but the admin landing route — but the mobile app is
        # refused at login, so returning nothing here is correct.
        role_key = normalize_permission_key(role_name)
        user_type_key = normalize_permission_key(user_type)
        is_web_admin = (
            user_type_key in {"platform", "staff", "contractor"}
            and any(token in role_key for token in ("admin", "superadmin", "platform"))
        ) or user_type_key == "platform"
        if is_web_admin:
            return [{
                "key": "admin",
                "label": "Admin",
                "route": "/admin/home",
                "isDefault": True,
            }]
        return []

    preferred = normalize_permission_key(app_module)
    if preferred in granted:
        granted.remove(preferred)
        granted.insert(0, preferred)

    surfaces = []
    for index, key in enumerate(granted):
        config = APP_SURFACE_CONFIG.get(key)
        if not config:
            continue
        surfaces.append({
            "key": key,
            "label": config["label"],
            "route": config["route"],
            "isDefault": index == 0,
        })
    return surfaces


def build_landing(app_surfaces, module_access):
    if not app_surfaces:
        return None

    first_module = next(
        (module for module in module_access if module.get("screens")),
        None,
    )
    first_screen = None
    if first_module:
        first_screen = next(
            (screen for screen in first_module.get("screens", []) if screen.get("permissions")),
            None,
        )

    primary_surface = app_surfaces[0]
    return {
        "surfaceKey": primary_surface["key"],
        "route": primary_surface["route"],
        "moduleKey": first_module.get("moduleKey") if first_module else None,
        "screenKey": first_screen.get("screenKey") if first_screen else None,
    }


def build_permission_version(
    permissions,
    column_permissions,
    *,
    app_modules=None,
    app_screens=None,
):
    raw_payload = json.dumps(
        {
            "permissions": permissions or {},
            "columns": (column_permissions or {}).get("flat", []),
            "app_modules": app_modules or [],
            "app_screens": app_screens or {},
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()[:16]


def finalize_permission_payload(
    payload,
    *,
    permissions=None,
    role_name=None,
    user_type=None,
    app_module=None,
    app_modules=None,
):
    effective_permissions = permissions if permissions is not None else payload.get("permissions", {})
    if permissions is not None and effective_permissions != payload.get("permissions", {}):
        module_access = build_fallback_module_access(effective_permissions)
    else:
        module_access = payload.get("module_access") or build_fallback_module_access(
            effective_permissions
        )

    app_surfaces = infer_app_surfaces(
        module_access,
        effective_permissions,
        role_name=role_name,
        user_type=user_type,
        app_module=app_module,
        app_modules=app_modules if app_modules is not None else payload.get("app_modules"),
    )

    return {
        **payload,
        "permissions": effective_permissions,
        "module_access": module_access,
        "app_surfaces": app_surfaces,
        "landing": build_landing(app_surfaces, module_access),
        "permission_version": build_permission_version(
            effective_permissions,
            payload.get("column_permissions", {}),
            app_modules=app_modules if app_modules is not None else payload.get("app_modules"),
            app_screens=payload.get("app_screens"),
        ),
        "generated_at": timezone.now().isoformat(),
    }


def permission_querysets(
    *,
    company_unique_id=None,
    staff_unique_id=None,
    include_all=False,
    **_unused,
):
    """
    Resolve the effective (action_queryset, column_queryset) for a request.

    - include_all=True: platform superadmin — the full CompanyUserScreenPermission
      catalog across all companies/projects (column permissions are not scoped
      by role anymore, so an empty queryset is returned for the "all" column view
      since there is no single project to key it to).
    - staff_unique_id given: resolve the staff's own StaffAccessConfiguration grant
      (a subset of whatever their project's CompanyUserScreenPermission catalog
      enabled). This is now the actual enforcement source for staff/contractor logins.
    """
    if include_all:
        action_queryset = CompanyUserScreenPermission.objects.filter(
            is_active=True,
            is_deleted=False,
        ).select_related("mainscreen_id", "userscreen_id", "userscreenaction_id")
        column_queryset = CompanyUserScreenColumnPermission.objects.filter(
            is_active=True,
            is_deleted=False,
        ).select_related("userscreen_id", "userscreen_id__mainscreen_id", "column_id")
        return action_queryset, column_queryset

    empty_action = StaffAccessConfigurationPermission.objects.none()
    empty_column = CompanyUserScreenColumnPermission.objects.none()

    if not staff_unique_id:
        return empty_action, empty_column

    config = (
        StaffAccessConfiguration.objects.filter(
            staff_id_id=staff_unique_id,
            is_active=True,
            is_deleted=False,
        )
        .first()
    )
    if not config:
        return empty_action, empty_column

    action_queryset = StaffAccessConfigurationPermission.objects.filter(
        staff_access_configuration_id_id=config.unique_id,
        is_active=True,
        is_deleted=False,
    ).select_related("mainscreen_id", "userscreen_id", "userscreenaction_id")

    column_queryset = CompanyUserScreenColumnPermission.objects.filter(
        company_id_id=config.company_id_id,
        userscreen_id_id__in=action_queryset.values_list("userscreen_id_id", flat=True),
        is_active=True,
        is_deleted=False,
    )
    # No projects configured => unrestricted access to every project under
    # the company, so don't narrow by project at all.
    project_ids = list(config.projects.values_list("unique_id", flat=True))
    if project_ids:
        column_queryset = column_queryset.filter(project_id_id__in=project_ids)
    column_queryset = column_queryset.select_related(
        "userscreen_id", "userscreen_id__mainscreen_id", "column_id"
    )

    return action_queryset, column_queryset


def role_key(role_name):
    normalized = normalize_permission_key(role_name)
    for key in ROLE_SCREEN_TEMPLATES:
        if key in normalized:
            return key
    return None


def role_default_permissions(role_name):
    """Compatibility baseline for mobile roles while strict mode is off."""
    key = role_key(role_name)
    if not key:
        return {}
    return ROLE_SCREEN_TEMPLATES.get(key, {})


def apply_role_defaults(permissions, role_name):
    """Merge a role template into explicit grants without removing anything."""
    defaults = role_default_permissions(role_name)
    if not defaults:
        return permissions

    merged = {
        module: {
            screen: list(actions)
            for screen, actions in (screens or {}).items()
        }
        for module, screens in (permissions or {}).items()
    }
    for module_name, screens in defaults.items():
        module_perms = merged.setdefault(module_name, {})
        for screen_name, actions in screens.items():
            existing = set(module_perms.get(screen_name, []))
            module_perms[screen_name] = sorted(existing.union(actions))
    return merged


def fallback_app_module(role_name, app_module):
    preferred = normalize_permission_key(app_module)
    if preferred in APP_SURFACE_KEYS:
        return preferred
    key = role_key(role_name)
    if key in APP_SURFACE_KEYS:
        return key
    return None


def staff_access_config(staff_unique_id):
    """The staff member's active access configuration, or None."""
    if not staff_unique_id:
        return None
    return StaffAccessConfiguration.objects.filter(
        staff_id_id=staff_unique_id,
        is_active=True,
        is_deleted=False,
    ).first()


def staff_app_modules(config):
    """Surface keys ticked on a StaffAccessConfiguration."""
    if config is None:
        return []
    return list(
        config.app_modules.filter(is_active=True, is_deleted=False)
        .values_list("surface_key", flat=True)
    )


def resolve_permission_payload(**filters):
    action_queryset, column_queryset = permission_querysets(**filters)
    config = staff_access_config(filters.get("staff_unique_id"))
    strict = bool(config and config.enforce_strict_permissions)

    # ONE permission list. A screen ticked here governs the web screen and the
    # mobile screen alike. While strict mode is off, mobile-role templates are
    # a compatibility floor so a partial web configuration cannot remove an
    # existing Driver/Operator/Supervisor flow. Once strict mode is enabled for
    # a staff member, the checked boxes are the whole of their access.
    permissions = build_action_permissions(action_queryset)
    if not strict:
        permissions = apply_role_defaults(permissions, filters.get("role_name"))

    app_modules = filters.get("app_modules")
    if app_modules is None:
        app_modules = staff_app_modules(config)
        if not app_modules and not strict:
            fallback = fallback_app_module(
                filters.get("role_name"),
                filters.get("app_module"),
            )
            app_modules = [fallback] if fallback else []

    citizen_screens = filters.get("citizen_screens")
    app_module = filters.get("app_module")

    # Which mobile screens the app should render, derived from the same
    # permissions the middleware enforces, so a visible tab and a 403 can
    # never disagree.
    screens = {}
    for surface in app_modules:
        screens[surface] = visible_screens(
            permissions, surface, citizen_screens=citizen_screens
        )

    payload = {
        "app_modules": app_modules,
        "app_screens": screens,
        "permission_details": build_permission_details(action_queryset, column_queryset),
        "column_permissions": build_column_permissions(column_queryset),
        "module_access": build_module_access(action_queryset, column_queryset),
        "permissions": permissions,
    }
    return finalize_permission_payload(
        payload,
        role_name=filters.get("role_name"),
        user_type=filters.get("user_type"),
        app_module=app_module,
        app_modules=app_modules,
    )
