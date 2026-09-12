# Hand-written — not a plain `makemigrations` output. See
# 0002_employee_face_embedding.py for the full explanation of why this
# project commits small hand-written migrations instead of relying on
# `0001_initial.py` (gitignored, machine-regenerated per environment).
#
# WHAT IT ADDS: `WasteCollection.image` — a best-effort proof photo carried
# over from the legacy WasteCollectionSub row(s) a collection was bridged
# from (see WasteCollectionBluetoothViewSet._sync_to_household_collection).
# Lets the driver app's "eye" button (waste-breakdown popup on a collected
# household stop) show the photo the driver actually captured, instead of
# weight-only. Nullable, no backfill: existing rows simply have no photo,
# same as a collection made without one.
#
# Same `information_schema`-guarded, idempotent pattern as
# 0002_employee_face_embedding.py — safe whether this environment's own
# regenerated `0001_initial.py` already has the column or not.

from django.db import migrations, models

TABLE = "app_wastecollection"
COLUMN = "image"


def add_image_column_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            [TABLE, COLUMN],
        )
        already_present = cursor.fetchone()[0] > 0

    if not already_present:
        schema_editor.execute(
            f"ALTER TABLE `{TABLE}` ADD COLUMN `{COLUMN}` varchar(255) NULL"
        )


def noop_reverse(apps, schema_editor):
    # Not dropping the column on reverse — see 0002's noop_reverse for why:
    # other environments never had this migration create it (it arrived via
    # their regenerated 0001_initial), so there is no single "undo" that is
    # correct everywhere. Leaving a nullable column in place is harmless.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_employee_face_embedding"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="wastecollection",
                    name="image",
                    field=models.CharField(
                        max_length=255,
                        blank=True,
                        null=True,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_image_column_if_missing,
                    noop_reverse,
                ),
            ],
        ),
    ]
