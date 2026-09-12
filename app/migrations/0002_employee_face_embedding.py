# Hand-written — not a plain `makemigrations` output.
#
# WHY THIS EXISTS: `app/migrations/*` is gitignored except a hand-picked
# exception (see `.gitignore`), because `0001_initial.py` is a huge
# machine-generated snapshot every environment regenerates for itself and
# never shares. Two environments can both report "0001_initial applied"
# while their real schemas differ, since Django compares migration *names*
# only. A schema change that must ship everywhere therefore gets its own
# small, committed migration.
#
# WHAT IT ADDS: `Employee.face_embedding`, a JSON cache of the face vector
# for `image_path` (this project's reference-photo field — see
# `app/models/staff_creations/attendance.py`). Attendance needs it when it
# runs on an embedding-comparing provider (InsightFace); it stays NULL under
# CompreFace, which compares image files on its own server.
#
# This cannot be a bare `AddField`: an environment whose own `0001_initial.py`
# was regenerated *after* the field was added to the model already has the
# column, and `AddField` would fail there with "Duplicate column". The
# database operation below checks `information_schema` first and only adds
# the column when it is genuinely missing — safe to run unmodified on
# production (where it is missing) and on dev machines (where it usually is
# not). `SeparateDatabaseAndState` keeps Django's migration *state* correct
# either way, so later migrations still see the field.
#
# The column is nullable with no default: it is a derived cache, always
# rebuildable from `image_path`, so existing rows need no backfill. The first
# punch after switching providers recomputes and stores it.
#
# DEPLOYMENT: writing this file does not, by itself, change any database —
# it still has to be applied with `python manage.py migrate app
# 0002_employee_face_embedding` on every environment (dev machines included).
# Forgetting that step is exactly what took the whole attendance module down
# on iwms-government-backend when this same pattern shipped there first.

from django.db import migrations, models

TABLE = "app_employee"
COLUMN = "face_embedding"


def add_face_embedding_column_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            [TABLE, COLUMN],
        )
        already_present = cursor.fetchone()[0] > 0

    if not already_present:
        schema_editor.execute(
            f"ALTER TABLE `{TABLE}` ADD COLUMN `{COLUMN}` json NULL"
        )


def noop_reverse(apps, schema_editor):
    # Not dropping the column on reverse: other environments never had this
    # migration create it (it arrived via their regenerated 0001_initial), so
    # there is no single "undo" that is correct everywhere. Leaving a nullable
    # cache column in place is harmless.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="employee",
                    name="face_embedding",
                    field=models.JSONField(
                        blank=True,
                        null=True,
                        editable=False,
                        help_text=(
                            "Cached face vector derived from image_path. "
                            "Provider-specific; cleared and recomputed when "
                            "the reference image changes."
                        ),
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_face_embedding_column_if_missing,
                    noop_reverse,
                ),
            ],
        ),
    ]
