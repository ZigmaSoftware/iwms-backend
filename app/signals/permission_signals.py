"""
Writes the User Access Audit (PermissionAuditLog) for every place a
permission can be granted:

* CompanyUserScreenPermission        -> COMPANY_SCREEN
* CompanyUserScreenColumnPermission  -> COMPANY_COLUMN
* StaffAccessConfigurationPermission -> STAFF_SCREEN   (screen + action ticks)
* StaffAccessConfiguration           -> STAFF_APP      (the one mobile app)
* CustomerAccessConfiguration        -> CUSTOMER_APP / CUSTOMER_SCREEN

Each pre_save handler snapshots the row as it stood before the save, so the
post_save handler logs what changed and not only the latest state. A failure
to write the audit is logged and never breaks the save that triggered it.
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.superadmin.screen_management.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.utils.audit_context import current_permission_actor

logger = logging.getLogger(__name__)

_PREVIOUS = "_previous_permission_state"


def _stash_previous(instance, fields):
    if not instance.pk:
        return
    previous = type(instance).objects.filter(pk=instance.pk).values(*fields).first()
    if previous:
        setattr(instance, _PREVIOUS, previous)


def _pop_previous(instance):
    return instance.__dict__.pop(_PREVIOUS, None)


def _actor(instance):
    """account_id of whoever made the change: a staff_unique_id for staff, the
    User.unique_id for platform/company users. Rows stamped by their own
    screen win; otherwise the request-scoped actor set by the viewset."""
    return (
        getattr(instance, "updated_by_id", None)
        or current_permission_actor()
        or getattr(instance, "created_by_id", None)
    )


def _action_type(created, is_deleted):
    if created:
        return "CREATED"
    return "DELETED" if is_deleted else "UPDATED"


def _write(**fields):
    PermissionAuditLog.objects.create(**fields)


# ------------------------------------------------------------------
# Company screen / column permissions
# ------------------------------------------------------------------

@receiver(pre_save, sender=CompanyUserScreenPermission)
def _stash_company_screen(sender, instance, **kwargs):
    _stash_previous(instance, ("is_active", "is_deleted"))


@receiver(post_save, sender=CompanyUserScreenPermission)
def log_permission_change(sender, instance, created, **kwargs):
    previous = _pop_previous(instance)
    try:
        _write(
            source="COMPANY_SCREEN",
            company_id=instance.company_id,
            project_id=instance.project_id,
            mainscreen_id=instance.mainscreen_id,
            userscreen_id=instance.userscreen_id,
            userscreenaction_id=instance.userscreenaction_id,
            updated_by=_actor(instance),
            is_active=instance.is_active,
            is_deleted=instance.is_deleted,
            previous_is_active=previous["is_active"] if previous else None,
            previous_is_deleted=previous["is_deleted"] if previous else None,
            action_type=_action_type(created, instance.is_deleted),
        )
    except Exception:
        logger.exception(
            "Failed to write PermissionAuditLog for CompanyUserScreenPermission %s",
            instance.pk,
        )


@receiver(pre_save, sender=CompanyUserScreenColumnPermission)
def _stash_company_column(sender, instance, **kwargs):
    _stash_previous(instance, ("can_view", "is_deleted"))


@receiver(post_save, sender=CompanyUserScreenColumnPermission)
def log_column_permission_change(sender, instance, created, **kwargs):
    previous = _pop_previous(instance)
    # can_view is the grant itself; a no-op resave is not worth a row.
    if previous and previous["can_view"] == instance.can_view and previous["is_deleted"] == instance.is_deleted:
        return
    try:
        _write(
            source="COMPANY_COLUMN",
            company_id=instance.company_id,
            project_id=instance.project_id,
            mainscreen_id=_mainscreen_of(instance.userscreen_id),
            userscreen_id=instance.userscreen_id,
            column_id=instance.column_id,
            updated_by=_actor(instance),
            is_active=instance.can_view and not instance.is_deleted,
            is_deleted=instance.is_deleted,
            previous_is_active=(previous["can_view"] and not previous["is_deleted"]) if previous else None,
            previous_is_deleted=previous["is_deleted"] if previous else None,
            action_type=_action_type(created, instance.is_deleted),
        )
    except Exception:
        logger.exception(
            "Failed to write PermissionAuditLog for CompanyUserScreenColumnPermission %s",
            instance.pk,
        )


# ------------------------------------------------------------------
# Staff Access Configuration
# ------------------------------------------------------------------

def _staff_scope(config):
    """(company_id, project_id, staff_id) of a staff configuration. A staff
    member scoped to several projects is logged without a single project."""
    if not config:
        return None, None, None
    projects = config.get_project_ids()
    return config.company_id, projects[0] if len(projects) == 1 else None, config.staff_id


@receiver(pre_save, sender=StaffAccessConfigurationPermission)
def _stash_staff_screen(sender, instance, **kwargs):
    _stash_previous(instance, ("is_active", "is_deleted"))


@receiver(post_save, sender=StaffAccessConfigurationPermission)
def log_staff_permission_change(sender, instance, created, **kwargs):
    previous = _pop_previous(instance)
    try:
        company_id, project_id, staff_id = _staff_scope(instance.staff_access_configuration)
        _write(
            source="STAFF_SCREEN",
            target_id=staff_id,
            company_id=company_id,
            project_id=project_id,
            mainscreen_id=instance.mainscreen_id,
            userscreen_id=instance.userscreen_id,
            userscreenaction_id=instance.userscreenaction_id,
            updated_by=_actor(instance),
            is_active=instance.is_active,
            is_deleted=instance.is_deleted,
            previous_is_active=previous["is_active"] if previous else None,
            previous_is_deleted=previous["is_deleted"] if previous else None,
            action_type=_action_type(created, instance.is_deleted),
        )
    except Exception:
        logger.exception(
            "Failed to write PermissionAuditLog for StaffAccessConfigurationPermission %s",
            instance.pk,
        )


@receiver(pre_save, sender=StaffAccessConfiguration)
def _stash_staff_app(sender, instance, **kwargs):
    _stash_previous(instance, ("app_module_id", "is_deleted"))


@receiver(post_save, sender=StaffAccessConfiguration)
def log_staff_app_change(sender, instance, created, **kwargs):
    """One row per app granted or revoked. Deleting the configuration revokes
    the app it held."""
    previous = _pop_previous(instance)
    before = None
    if previous and not previous["is_deleted"]:
        before = previous["app_module_id"]
    after = None if instance.is_deleted else instance.app_module_id
    if before == after:
        return
    try:
        company_id, project_id, staff_id = _staff_scope(instance)
        common = dict(
            source="STAFF_APP",
            target_id=staff_id,
            company_id=company_id,
            project_id=project_id,
            updated_by=_actor(instance),
        )
        if before:
            _write(
                **common,
                app_module_id=before,
                is_active=False,
                is_deleted=True,
                previous_is_active=True,
                previous_is_deleted=False,
                action_type="DELETED",
            )
        if after:
            _write(
                **common,
                app_module_id=after,
                is_active=True,
                is_deleted=False,
                action_type="CREATED",
            )
    except Exception:
        logger.exception(
            "Failed to write PermissionAuditLog for StaffAccessConfiguration %s",
            instance.pk,
        )


# ------------------------------------------------------------------
# Customer Access Configuration
# ------------------------------------------------------------------

def _mainscreen_of(userscreen_id):
    if not userscreen_id:
        return None
    return (
        UserScreen.objects.filter(unique_id=userscreen_id)
        .values_list("mainscreen_id", flat=True)
        .first()
    )


@receiver(pre_save, sender=CustomerAccessConfiguration)
def _stash_customer_access(sender, instance, **kwargs):
    _stash_previous(instance, ("app_modules", "app_screens", "is_deleted"))


@receiver(post_save, sender=CustomerAccessConfiguration)
def log_customer_access_change(sender, instance, created, **kwargs):
    """App modules and app screens are id lists on one row, so each id added
    or removed gets its own audit row. Deleting the configuration revokes
    everything it held."""
    previous = _pop_previous(instance)
    try:
        common = dict(
            target_id=instance.customer_id,
            company_id=instance.company_id,
            project_id=_customer_project(instance.customer_id),
            updated_by=_actor(instance),
        )
        for field, source, id_field in (
            ("app_modules", "CUSTOMER_APP", "app_module_id"),
            ("app_screens", "CUSTOMER_SCREEN", "userscreen_id"),
        ):
            before = set()
            if previous and not previous["is_deleted"]:
                before = set(previous[field] or [])
            after = set() if instance.is_deleted else set(getattr(instance, field) or [])

            for granted, ids in ((True, after - before), (False, before - after)):
                for item_id in sorted(ids):
                    extra = {id_field: item_id}
                    if id_field == "userscreen_id":
                        extra["mainscreen_id"] = _mainscreen_of(item_id)
                    _write(
                        **common,
                        **extra,
                        source=source,
                        is_active=granted,
                        is_deleted=not granted,
                        previous_is_active=None if granted else True,
                        previous_is_deleted=None if granted else False,
                        action_type="CREATED" if granted else "DELETED",
                    )
    except Exception:
        logger.exception(
            "Failed to write PermissionAuditLog for CustomerAccessConfiguration %s",
            instance.pk,
        )


def _customer_project(customer_id):
    from app.models.masters.customer_masters.customercreation import CustomerCreation

    if not customer_id:
        return None
    return (
        CustomerCreation.objects.filter(unique_id=customer_id)
        .values_list("project_id", flat=True)
        .first()
    )
