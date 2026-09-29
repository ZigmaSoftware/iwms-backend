"""Repair `company_id` columns that hold a company's NAME instead of its unique_id.

Every `company_id` is a plain CharField holding the Company's unique_id. When
a seeder hands one a Company *instance* instead (e.g.
`Project.objects.update_or_create(company_id=company, ...)`), Django stores
`str(company)` — the company's name, "Blue Planet" — and every row copied
from it (staff, trip plans, daily trips, screen permissions, ...) inherits
the bad value. Those rows then never match `?company_unique_id=CMP-...`, so
e.g. the project dropdown on reports/weighbridge pages comes back empty.

This rewrites every such value to the matching company's unique_id.

    python manage.py backfill_company_ids            # show what it would do
    python manage.py backfill_company_ids --apply

Only exact company-name matches are touched, so it is safe to re-run.
"""

from django.apps import apps
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, models, transaction

from app.models.superadmin_masters.company import Company


class Command(BaseCommand):
    help = "Rewrite company_id values that hold a company name to that company's unique_id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without it, only report what would change.",
        )

    def _repair(self, qs, uid):
        try:
            with transaction.atomic():
                qs.update(company_id=uid)
            return
        except IntegrityError:
            pass

        # A company-scoped unique key collided: the bad rows were numbered in
        # their own "company" (e.g. staff_id STF0001 issued under "Blue
        # Planet" while the real company already has an STF0001). Save row
        # by row instead, so the model's own save() re-issues the scoped id
        # when it sees the scope change (see StaffcreationOfficeDetails.save).
        for obj in list(qs):
            obj.company_id = uid
            try:
                with transaction.atomic():
                    obj.save()
            except IntegrityError as exc:
                self.failed += 1
                self.stderr.write(f"    could not repair {type(obj).__name__} {obj.pk}: {exc}")

    def handle(self, *args, **options):
        apply = options["apply"]
        self.failed = 0

        name_to_uid = {}
        for uid, name in Company.objects.values_list("unique_id", "name"):
            if name and name != uid:
                name_to_uid.setdefault(name, uid)
        if not name_to_uid:
            self.stdout.write("No companies found.")
            return

        total = 0
        with transaction.atomic():
            for model in apps.get_app_config("app").get_models():
                try:
                    field = model._meta.get_field("company_id")
                except Exception:
                    continue
                if not isinstance(field, models.CharField):
                    continue

                # all_objects (where present) also covers soft-deleted rows.
                manager = getattr(model, "all_objects", model._default_manager)
                for name, uid in name_to_uid.items():
                    qs = manager.filter(company_id=name)
                    count = qs.count()
                    if not count:
                        continue
                    total += count
                    self.stdout.write(
                        f"  {model.__name__:36} {count:6}  '{name}' -> {uid}"
                    )
                    if apply:
                        self._repair(qs, uid)

            # Raised inside the atomic block so a partial repair rolls back.
            if self.failed:
                raise CommandError(
                    f"{self.failed} rows could not be repaired — nothing was written."
                )

        if not total:
            self.stdout.write(self.style.SUCCESS("Nothing to repair."))
            return

        if apply:
            # Bulk .update() bypasses the model-level cache invalidation.
            cache.clear()
            self.stdout.write(self.style.SUCCESS(f"Repaired {total} rows."))
        else:
            self.stdout.write(
                self.style.WARNING(f"{total} rows would change. Re-run with --apply.")
            )
