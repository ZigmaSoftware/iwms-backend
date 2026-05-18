from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission


ACTION_KEYS = ("show", "view", "add", "edit", "delete")


def base_action_map():
    return {action: False for action in ACTION_KEYS}


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
                "userScreenId": perm.userscreen_id_id,
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
                    "userScreenId": screen_id,
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
            "userTypeId": column_permission.usertype_id_id,
            "staffUserTypeId": column_permission.staffusertype_id_id,
            "mainScreenId": mainscreen.unique_id,
            "mainScreenName": mainscreen.mainscreen_name,
            "userScreenId": userscreen.unique_id,
            "userScreenName": userscreen.userscreen_name,
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


def permission_querysets(
    *,
    company_unique_id=None,
    usertype_unique_id=None,
    staffusertype_unique_id=None,
    include_all=False,
):
    action_queryset = CompanyUserScreenPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    ).select_related(
        "mainscreen_id",
        "userscreen_id",
        "userscreenaction_id",
    )
    column_queryset = CompanyUserScreenColumnPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    ).select_related(
        "userscreen_id",
        "userscreen_id__mainscreen_id",
        "column_id",
    )

    if include_all:
        return action_queryset, column_queryset

    if not company_unique_id or not usertype_unique_id:
        return action_queryset.none(), column_queryset.none()

    filters = {
        "company_id_id": company_unique_id,
        "usertype_id_id": usertype_unique_id,
    }
    if staffusertype_unique_id:
        filters["staffusertype_id_id"] = staffusertype_unique_id
    else:
        filters["staffusertype_id__isnull"] = True

    return action_queryset.filter(**filters), column_queryset.filter(**filters)


def resolve_permission_payload(**filters):
    action_queryset, column_queryset = permission_querysets(**filters)
    return {
        "permissions": build_action_permissions(action_queryset),
        "permission_details": build_permission_details(action_queryset, column_queryset),
        "column_permissions": build_column_permissions(column_queryset),
    }
