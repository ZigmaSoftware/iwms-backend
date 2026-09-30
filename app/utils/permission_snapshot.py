"""
One User Access Audit record per access save.

Staff and Customer Access Configuration save a person's whole permission set
at once, so their audit is not one row per tick: the viewset snapshots the
person's access before and after the save and stores both on a single
PermissionAuditLog row (old_permissions / new_permissions), along with the
HTTP method of the request.

A snapshot stores names as well as ids, so the trail stays readable after a
screen or action is renamed or removed:

    {
      "app_modules": [{"id": "...", "name": "Driver"}],
      "modules": [
        {"id": "MS-1", "name": "masters", "screens": [
          {"id": "US-1", "name": "plants", "actions": [
            {"id": "ACT-1", "name": "add"}, ...
          ]}
        ]}
      ]
    }

Customer screens carry no actions: the screen itself is the grant.
"""

import logging

from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.utils.audit_context import resolve_actor

logger = logging.getLogger(__name__)

EMPTY_SNAPSHOT = {"app_modules": [], "modules": []}


def _names(model, ids, name_field):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    return dict(
        model.objects.filter(unique_id__in=ids).values_list("unique_id", name_field)
    )


def _app_modules(ids):
    names = _names(AppModule, ids, "label")
    return [{"id": i, "name": names.get(i) or i} for i in ids if i]


def _build_modules(grants, item_names=None):
    """grants: iterable of (mainscreen_id, userscreen_id or None, item_id or
    None). An item is a screen action, or a column when item_names (id ->
    name) is given. A grant with no screen is a whole-module grant."""
    grants = list(grants)
    screen_ids = {g[1] for g in grants if g[1]}
    screens = {
        row["unique_id"]: row
        for row in UserScreen.objects.filter(unique_id__in=screen_ids).values(
            "unique_id", "userscreen_name", "mainscreen_id", "order_no"
        )
    }
    # A grant row may not carry its main screen; the screen always knows it.
    grants = [
        (m or screens.get(s, {}).get("mainscreen_id"), s, a) for m, s, a in grants
    ]
    module_rows = {
        row["unique_id"]: row
        for row in MainScreen.objects.filter(
            unique_id__in={g[0] for g in grants if g[0]}
        ).values("unique_id", "mainscreen_name", "order_no")
    }
    if item_names is None:
        item_names = _names(UserScreenAction, {g[2] for g in grants}, "action_name")

    tree = {}
    for mainscreen_id, userscreen_id, item_id in grants:
        module = tree.setdefault(mainscreen_id, {})
        if not userscreen_id:
            continue
        items = module.setdefault(userscreen_id, [])
        if item_id and all(i["id"] != item_id for i in items):
            items.append({"id": item_id, "name": item_names.get(item_id) or item_id})

    def module_order(mid):
        row = module_rows.get(mid) or {}
        return (row.get("order_no") or 0, row.get("mainscreen_name") or mid or "")

    def screen_order(sid):
        row = screens.get(sid) or {}
        return (row.get("order_no") or 0, row.get("userscreen_name") or sid or "")

    return [
        {
            "id": mid,
            "name": (module_rows.get(mid) or {}).get("mainscreen_name") or mid or "-",
            "screens": [
                {
                    "id": sid,
                    "name": (screens.get(sid) or {}).get("userscreen_name") or sid or "-",
                    "actions": sorted(tree[mid][sid], key=lambda a: a["name"]),
                }
                for sid in sorted(tree[mid], key=screen_order)
            ],
        }
        for mid in sorted(tree, key=module_order)
    ]


def staff_access_snapshot(config):
    """A staff member's app and screen/action grants, or an empty snapshot
    when they have no live configuration."""
    from app.models.superadmin.staff_management.staff_access_configuration import (
        StaffAccessConfigurationPermission,
    )

    if not config or config.is_deleted:
        return EMPTY_SNAPSHOT
    grants = StaffAccessConfigurationPermission.objects.filter(
        staff_access_configuration_id=config.unique_id, is_deleted=False
    ).values_list("mainscreen_id", "userscreen_id", "userscreenaction_id")
    return {
        "app_modules": _app_modules([config.app_module_id]),
        "modules": _build_modules(grants),
    }


def customer_access_snapshot(config):
    """A customer's apps and citizen app screens."""
    if not config or config.is_deleted:
        return EMPTY_SNAPSHOT
    return {
        "app_modules": _app_modules(list(config.app_modules or [])),
        "modules": _build_modules((None, sid, None) for sid in (config.app_screens or [])),
    }


def snapshot_keys(snapshot):
    """Every individual grant in a snapshot, as comparable keys."""
    snapshot = snapshot or EMPTY_SNAPSHOT
    keys = {("app", m["id"]) for m in snapshot.get("app_modules", [])}
    for module in snapshot.get("modules", []):
        if not module.get("screens"):
            keys.add(("module", module["id"]))
        for screen in module.get("screens", []):
            if screen.get("actions"):
                keys.update(("action", screen["id"], a["id"]) for a in screen["actions"])
            else:
                keys.add(("screen", screen["id"]))
    return keys


def snapshot_from_keys(keys, columns=False):
    """Inverse of snapshot_keys: rebuild a named snapshot from grant keys.
    With columns=True the items under a screen are UserScreenColumn ids."""
    apps = sorted(k[1] for k in keys if k[0] == "app")
    grants = [(None, k[1], k[2]) for k in keys if k[0] == "action"]
    grants += [(None, k[1], None) for k in keys if k[0] == "screen"]
    grants += [(k[1], None, None) for k in keys if k[0] == "module"]
    item_names = None
    if columns:
        item_names = _names(UserScreenColumn, {g[2] for g in grants}, "display_name")
    return {
        "app_modules": _app_modules(apps),
        "modules": _build_modules(grants, item_names),
    }


# ------------------------------------------------------------------
# Company screen / column permissions
# ------------------------------------------------------------------
# These are company-wide grants written by several endpoints, some through
# queryset.update() / bulk_create() that fire no model signals. So the
# screens that write them snapshot both tables when a write request starts
# and again when it succeeds, and store one row per company/project the
# request changed.

def company_permission_state():
    """{(source, company_id, project_id): grant keys} for every live
    company screen and column permission."""
    from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
        CompanyUserScreenColumnPermission,
    )
    from app.models.superadmin.screen_management.companyuserscreenpermission import (
        CompanyUserScreenPermission,
    )

    state = {}
    screen_rows = CompanyUserScreenPermission.objects.filter(
        is_active=True, is_deleted=False
    ).values_list("company_id", "project_id", "mainscreen_id", "userscreen_id", "userscreenaction_id")
    for company_id, project_id, mainscreen_id, userscreen_id, action_id in screen_rows:
        if action_id:
            key = ("action", userscreen_id, action_id)
        elif userscreen_id:
            key = ("screen", userscreen_id)
        else:
            key = ("module", mainscreen_id)
        state.setdefault(("COMPANY_SCREEN", company_id, project_id), set()).add(key)

    column_rows = CompanyUserScreenColumnPermission.objects.filter(
        can_view=True, is_deleted=False
    ).values_list("company_id", "project_id", "userscreen_id", "column_id")
    for company_id, project_id, userscreen_id, column_id in column_rows:
        state.setdefault(("COMPANY_COLUMN", company_id, project_id), set()).add(
            ("action", userscreen_id, column_id)
        )
    return state


def write_company_permission_audits(request, before, after):
    """One row per company/project whose grants differ between states."""
    for scope in sorted(set(before) | set(after), key=lambda k: tuple(str(p) for p in k)):
        old_keys, new_keys = before.get(scope, set()), after.get(scope, set())
        if old_keys == new_keys:
            continue
        source, company_id, project_id = scope
        columns = source == "COMPANY_COLUMN"
        write_access_audit(
            source=source,
            request=request,
            target_id=None,
            company_id=company_id,
            project_id=project_id,
            before=snapshot_from_keys(old_keys, columns=columns),
            after=snapshot_from_keys(new_keys, columns=columns),
            action_type=(
                "CREATED" if not old_keys else "DELETED" if not new_keys else "UPDATED"
            ),
        )


class CompanyPermissionAuditMixin:
    """For views that write company screen/column permissions: one User
    Access Audit row per company/project a successful write request changed."""

    AUDITED_METHODS = ("POST", "PUT", "PATCH", "DELETE")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in self.AUDITED_METHODS:
            self._company_permissions_before = company_permission_state()

    def finalize_response(self, request, response, *args, **kwargs):
        before = self.__dict__.pop("_company_permissions_before", None)
        if before is not None and getattr(response, "status_code", 500) < 400:
            try:
                write_company_permission_audits(request, before, company_permission_state())
            except Exception:
                logger.exception("Failed to write company permission audit")
        return super().finalize_response(request, response, *args, **kwargs)


def write_access_audit(
    *, source, request, target_id, company_id, project_id, before, after, action_type
):
    """Store one audit row for a save, unless it changed nothing."""
    old_keys, new_keys = snapshot_keys(before), snapshot_keys(after)
    if old_keys == new_keys and action_type != "DELETED":
        return None
    try:
        return PermissionAuditLog.objects.create(
            source=source,
            target_id=target_id,
            company_id=company_id,
            project_id=project_id,
            updated_by=resolve_actor(getattr(request, "user", None))[0],
            http_method=(getattr(request, "method", "") or "").upper() or None,
            old_permissions=before,
            new_permissions=after,
            is_active=bool(new_keys),
            is_deleted=action_type == "DELETED",
            previous_is_active=bool(old_keys),
            previous_is_deleted=False,
            action_type=action_type,
        )
    except Exception:
        logger.exception("Failed to write PermissionAuditLog for %s %s", source, target_id)
        return None
