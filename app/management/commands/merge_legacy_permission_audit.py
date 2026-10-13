"""
Merge per-change permission audit rows into one row per save.

Before saves were snapshotted, every ticked or unticked permission was its
own PermissionAuditLog row: STAFF_SCREEN / STAFF_APP / CUSTOMER_APP /
CUSTOMER_SCREEN for a person, and COMPANY_SCREEN / COMPANY_COLUMN rows with
no old/new permissions for a company. This command turns each save's rows
into a single row with the whole access before and after it (per person, or
per company/project), then removes the per-change rows.

Rows written within GAP_SECONDS of each other for the same person or
company/project count as one save. The full before/after is rebuilt by
walking back from the access as it stood after the last legacy save,
undoing each save's changes.

    python manage.py merge_legacy_permission_audit --dry-run
    python manage.py merge_legacy_permission_audit
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.utils.permission_snapshot import (
    company_permission_state,
    customer_access_snapshot,
    snapshot_from_keys,
    snapshot_keys,
    staff_access_snapshot,
)

GAP_SECONDS = 2

# family -> the legacy sources that merge into it
FAMILIES = {
    "STAFF_ACCESS": ("STAFF_SCREEN", "STAFF_APP"),
    "CUSTOMER_ACCESS": ("CUSTOMER_APP", "CUSTOMER_SCREEN"),
    "COMPANY_SCREEN": ("COMPANY_SCREEN",),
    "COMPANY_COLUMN": ("COMPANY_COLUMN",),
}
COMPANY_FAMILIES = ("COMPANY_SCREEN", "COMPANY_COLUMN")


def _row_key(row):
    if row.source in ("STAFF_APP", "CUSTOMER_APP"):
        return ("app", row.app_module_id)
    if row.source == "CUSTOMER_SCREEN":
        return ("screen", row.userscreen_id)
    if row.source == "COMPANY_COLUMN":
        return ("action", row.userscreen_id, row.column_id)
    if row.source == "COMPANY_SCREEN" and not row.userscreenaction_id:
        if row.userscreen_id:
            return ("screen", row.userscreen_id)
        return ("module", row.mainscreen_id)
    return ("action", row.userscreen_id, row.userscreenaction_id)


def _scope(family, row):
    """Whose access a legacy row belongs to."""
    if family in COMPANY_FAMILIES:
        return (row.company_id, row.project_id)
    return (row.target_id,)


def _split_saves(rows):
    saves, current = [], []
    for row in rows:
        if current and row.timestamp - current[-1].timestamp > timedelta(seconds=GAP_SECONDS):
            saves.append(current)
            current = []
        current.append(row)
    if current:
        saves.append(current)
    return saves


class Command(BaseCommand):
    help = "Merge per-change Staff/Customer access audit rows into one row per save."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only; change nothing.")

    def _access_after(self, family, scope, after_timestamp, company_state):
        """Keys of the access right after the last legacy save: the 'before'
        of the first snapshot row that followed it, else the live access."""
        later = PermissionAuditLog.objects.filter(
            source=family, old_permissions__isnull=False, timestamp__gt=after_timestamp
        )
        if family in COMPANY_FAMILIES:
            later = later.filter(company_id=scope[0], project_id=scope[1])
        else:
            later = later.filter(target_id=scope[0])
        later = later.order_by("timestamp", "id").first()
        if later is not None:
            return snapshot_keys(later.old_permissions)

        if family in COMPANY_FAMILIES:
            return set(company_state.get((family, *scope), set()))
        if family == "STAFF_ACCESS":
            config = StaffAccessConfiguration.objects.filter(
                staff_id=scope[0], is_deleted=False
            ).first()
            return snapshot_keys(staff_access_snapshot(config))
        config = CustomerAccessConfiguration.objects.filter(
            customer_id=scope[0], is_deleted=False
        ).first()
        return snapshot_keys(customer_access_snapshot(config))

    def handle(self, *args, dry_run=False, **options):
        merged_rows = created = 0
        company_state = company_permission_state()
        for family, legacy_sources in FAMILIES.items():
            # Legacy rows are the per-change ones: no old/new snapshot.
            legacy = PermissionAuditLog.objects.filter(
                source__in=legacy_sources, old_permissions__isnull=True
            ).order_by("timestamp", "id")
            by_scope = {}
            for row in legacy:
                by_scope.setdefault(_scope(family, row), []).append(row)

            for scope, rows in by_scope.items():
                saves = _split_saves(rows)
                new_keys = self._access_after(family, scope, rows[-1].timestamp, company_state)

                plan = []
                for save in reversed(saves):
                    granted = {_row_key(r) for r in save if r.is_active}
                    revoked = {_row_key(r) for r in save if not r.is_active}
                    old_keys = (new_keys - granted) | revoked
                    plan.append((save, old_keys, new_keys))
                    new_keys = old_keys

                label = " / ".join(str(part) for part in scope)
                self.stdout.write(f"{family} {label}: {len(rows)} rows -> {len(saves)} saves")
                merged_rows += len(rows)
                created += len(saves)
                if dry_run:
                    continue

                columns = family == "COMPANY_COLUMN"
                with transaction.atomic():
                    for save, old_keys, new_keys_for_save in plan:
                        last = save[-1]
                        if not new_keys_for_save:
                            action_type = "DELETED"
                        elif not old_keys:
                            action_type = "CREATED"
                        else:
                            action_type = "UPDATED"
                        row = PermissionAuditLog.objects.create(
                            source=family,
                            target_id=None if family in COMPANY_FAMILIES else scope[0],
                            company_id=last.company_id,
                            project_id=last.project_id,
                            updated_by=last.updated_by,
                            http_method=last.http_method,
                            old_permissions=snapshot_from_keys(old_keys, columns=columns),
                            new_permissions=snapshot_from_keys(new_keys_for_save, columns=columns),
                            is_active=bool(new_keys_for_save),
                            is_deleted=action_type == "DELETED",
                            previous_is_active=bool(old_keys),
                            previous_is_deleted=False,
                            action_type=action_type,
                        )
                        # timestamp is auto_now_add; keep the save's own time.
                        PermissionAuditLog.objects.filter(pk=row.pk).update(
                            timestamp=last.timestamp
                        )
                    PermissionAuditLog.objects.filter(pk__in=[r.pk for r in rows]).delete()

        verb = "Would merge" if dry_run else "Merged"
        self.stdout.write(self.style.SUCCESS(f"{verb} {merged_rows} rows into {created} saves."))
