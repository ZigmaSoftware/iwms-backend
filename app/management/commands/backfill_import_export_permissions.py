"""Backfill the dedicated "import" and "export" screen permissions.

Bulk uploads (POST .../bulk-upload/) now need "import" as well as "add", and
Excel exports (POST /api/v1/exports/excel/) need "export" on the exported
list. To keep everyone's current access this grants, once and idempotently:

    add  -> import
    view -> export

on both grant tables: the company/project catalog
(CompanyUserScreenPermission) and the per-staff grants
(StaffAccessConfigurationPermission). The catalog is done first, so the
staff grants it adds are always backed by a catalog row.

Screens whose catalog entry restricts its actions (dashboards are
view-only), superadmin-only screens and the citizen app screens are skipped:
the catalog does not offer import/export there, and the permission seeder
would retire such grants anyway.

It also makes sure the "import" and "export" UserScreenAction rows exist.

    python manage.py backfill_import_export_permissions          # dry run
    python manage.py backfill_import_export_permissions --apply  # write
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfigurationPermission,
)
from app.utils.app_feature_grants import CITIZEN_APP_MAINSCREEN
from app.utils.permission_catalog import SCREEN_ACTIONS, SUPERADMIN_ONLY_SCREENS

MAPPINGS = (("add", "import"), ("view", "export"))

# Fields identifying "the same grant" on each table, besides the action
# (mirrors each table's active-row unique constraint).
KEY_FIELDS = {
    CompanyUserScreenPermission: (
        "company_id",
        "project_id",
        "mainscreen_id",
        "permission_type",
        "userscreen_id",
    ),
    StaffAccessConfigurationPermission: (
        "staff_access_configuration_id",
        "userscreen_id",
    ),
}

COPY_EXCLUDE = {"unique_id", "id", "created_at", "updated_at"}


class Command(BaseCommand):
    help = "Grant import where add is granted and export where view is granted."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the grants (default is a dry run).",
        )

    @staticmethod
    def _action_id(name):
        row = (
            UserScreenAction.objects.filter(is_deleted=False)
            .filter(Q(variable_name__iexact=name) | Q(action_name__iexact=name))
            .order_by("unique_id")
            .first()
        )
        return row.unique_id if row else None

    @staticmethod
    def _excluded_screen_ids(target):
        """Screens on which the catalog does not offer `target`."""
        excluded = set()
        names = {
            name for name, allowed in SCREEN_ACTIONS.items() if target not in allowed
        } | set(SUPERADMIN_ONLY_SCREENS)
        excluded.update(
            UserScreen.objects.filter(userscreen_name__in=names).values_list(
                "unique_id", flat=True
            )
        )
        citizen_mains = MainScreen.objects.filter(
            mainscreen_name=CITIZEN_APP_MAINSCREEN
        ).values_list("unique_id", flat=True)
        excluded.update(
            UserScreen.objects.filter(mainscreen_id__in=list(citizen_mains)).values_list(
                "unique_id", flat=True
            )
        )
        return excluded

    def _ensure_actions(self, apply):
        for name in ("import", "export"):
            existing = UserScreenAction.objects.filter(
                Q(action_name__iexact=name) | Q(variable_name__iexact=name)
            ).first()
            if existing and not existing.is_deleted and existing.is_active:
                continue
            if not apply:
                self.stdout.write(f'UserScreenAction "{name}": to create/restore')
                continue
            if existing:
                existing.is_active = True
                existing.is_deleted = False
                existing.save(update_fields=["is_active", "is_deleted"])
            else:
                UserScreenAction.objects.create(
                    action_name=name, variable_name=name, is_active=True, is_deleted=False
                )
            self.stdout.write(f'UserScreenAction "{name}": created/restored')

    def handle(self, *args, **options):
        apply = options["apply"]

        with transaction.atomic():
            self._ensure_actions(apply)

            ids = {name: self._action_id(name) for pair in MAPPINGS for name in pair}
            missing = [name for name, value in ids.items() if not value]
            if missing and apply:
                self.stdout.write(
                    self.style.ERROR(f"Could not resolve actions: {', '.join(missing)}")
                )
                return

            total = 0
            for model, label in (
                (CompanyUserScreenPermission, "company/project catalog"),
                (StaffAccessConfigurationPermission, "staff"),
            ):
                key_fields = KEY_FIELDS[model]
                copy_fields = [
                    f.name
                    for f in model._meta.concrete_fields
                    if f.name not in COPY_EXCLUDE and f.editable
                ]
                for source, target in MAPPINGS:
                    if not ids[source]:
                        continue
                    excluded = self._excluded_screen_ids(target)
                    made = 0
                    rows = (
                        model.objects.filter(
                            is_deleted=False, userscreenaction_id=ids[source]
                        )
                        .exclude(userscreen_id__in=excluded)
                        .order_by("pk")
                    )
                    for row in rows.iterator():
                        if ids[target]:
                            twin = {field: getattr(row, field) for field in key_fields}
                            if model.objects.filter(
                                is_deleted=False,
                                userscreenaction_id=ids[target],
                                **twin,
                            ).exists():
                                continue
                        if apply:
                            data = {field: getattr(row, field) for field in copy_fields}
                            data["userscreenaction_id"] = ids[target]
                            if data.get("description"):
                                rest = (data["description"].split(" ", 1) + [""])[1]
                                data["description"] = f"{target} {rest}".strip()
                            model.objects.create(**data)
                        made += 1
                    self.stdout.write(
                        f"{label} grants: {source} -> {target}: "
                        f"{made} {'created' if apply else 'to create'}"
                    )
                    total += made

        if apply and total:
            # Permission payloads are cached (login + middleware).
            cache.clear()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {total} grants "
                f"{'created' if apply else 'to create (dry run - rerun with --apply)'}."
            )
        )
