# core/management/commands/seeders/base.py
from django.db import transaction

class BaseSeeder:
    name = "base"

    @transaction.atomic
    def run(self):
        raise NotImplementedError("---Seeder must implement run()---")

    def log(self, message):
        print(f"[{self.name.upper()}] {message}")

    def log_error(self, message):
        print(f"[{self.name.upper()} ERROR] {message}")


def uid(obj):
    """unique_id of a model instance; strings/None pass through unchanged.

    company_id/project_id are plain CharFields, so passing an instance would
    store str(obj) — e.g. the company NAME — instead of its unique_id, and the
    row would never match a `company_unique_id=CMP-...` filter.
    """
    return getattr(obj, "unique_id", obj)
