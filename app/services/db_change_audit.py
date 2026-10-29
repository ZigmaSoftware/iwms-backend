"""
DB Change Audit: database triggers that record INSERT/UPDATE/DELETE made on
the database directly (a SQL client, a script, phpMyAdmin), into
DbChangeAudit / `db_change_audit`.

How app writes are kept out: every connection Django opens runs
`SET @iwms_app_write = 1` (mark_app_connection), and the triggers only log
when that session variable is unset. App writes are already audited in
CommonAudit by AuditViewSetMixin, so they are not logged twice.

Triggers name every column of their table, so a migration that drops or
renames a column would break them. They are dropped before `migrate`
(pre_migrate) and rebuilt from the new schema after it (post_migrate); see
ApiConfig.ready. `manage.py install_db_audit_triggers` does the same by hand.

MySQL/MariaDB only. Limits of the approach, inherent to triggers:
  * TRUNCATE and DROP TABLE do not fire triggers and are not recorded.
  * A session that runs `SET @iwms_app_write = 1` itself is not recorded.
  * Changes made while the triggers are dropped (during `migrate`) are not
    recorded.
"""

import hashlib
import logging
import os

from django.db import connections

logger = logging.getLogger(__name__)

APP_SESSION_VAR = "@iwms_app_write"
AUDIT_TABLE = "db_change_audit"
TRIGGER_PREFIX = "dbaudit_"

# Never audited: the audit table itself (a trigger can't write to the table
# it fires on), and Django bookkeeping that is not business data.
EXCLUDED_TABLES = frozenset({AUDIT_TABLE, "django_migrations", "django_session"})

# Binary/spatial values don't belong in a JSON snapshot; the column is still
# checked for changes, only its value is left out of old_data/new_data.
_UNSERIALIZABLE_TYPES = frozenset({
    "binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob",
    "geometry", "point", "linestring", "polygon", "multipoint",
    "multilinestring", "multipolygon", "geometrycollection",
})

_OPERATIONS = (
    ("INSERT", "ins"),
    ("UPDATE", "upd"),
    ("DELETE", "del"),
)


def is_enabled(connection=None):
    connection = connection or connections["default"]
    if connection.vendor != "mysql":
        return False
    return os.getenv("DB_CHANGE_AUDIT_ENABLED", "true").strip().lower() not in ("0", "false", "no")


def mark_app_connection(sender, connection, **kwargs):
    """connection_created receiver: tags the session as the app's own, so
    the triggers skip everything written through Django."""
    if connection.vendor != "mysql":
        return
    with connection.cursor() as cursor:
        cursor.execute(f"SET {APP_SESSION_VAR} = 1")


def _quote(name):
    return "`" + name.replace("`", "``") + "`"


def _literal(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _trigger_name(table, suffix):
    name = f"{TRIGGER_PREFIX}{table}_{suffix}"
    if len(name) <= 64:
        return name
    digest = hashlib.md5(table.encode()).hexdigest()[:12]
    return f"{TRIGGER_PREFIX}{table[:40]}_{digest}_{suffix}"


def _row_json(columns, row):
    pairs = ", ".join(
        f"{_literal(name)}, {row}.{_quote(name)}"
        for name, data_type, _ in columns
        if data_type not in _UNSERIALIZABLE_TYPES
    )
    return f"JSON_OBJECT({pairs})"


def _object_id_expr(columns, row):
    names = [name for name, _, _ in columns]
    if "unique_id" in names:
        return f"{row}.`unique_id`"
    pk = [name for name, _, key in columns if key == "PRI"]
    if not pk:
        return "NULL"
    return "CONCAT_WS('/', " + ", ".join(f"{row}.{_quote(n)}" for n in pk) + ")"


def _tenancy_expr(columns, row, column):
    return f"{row}.{_quote(column)}" if any(n == column for n, _, _ in columns) else "NULL"


def build_trigger_sql(table, columns):
    """CREATE TRIGGER statements (one per operation) for `table`.
    `columns` is [(column_name, data_type, column_key), ...]."""
    statements = []
    for operation, suffix in _OPERATIONS:
        row = "OLD" if operation == "DELETE" else "NEW"
        old_data = _row_json(columns, "OLD") if operation != "INSERT" else "NULL"
        new_data = _row_json(columns, "NEW") if operation != "DELETE" else "NULL"
        insert = (
            f"INSERT INTO {_quote(AUDIT_TABLE)} (table_name, operation, object_id, "
            f"company_id, project_id, old_data, new_data, changed_columns, "
            f"db_user, db_account, connection_id, changed_at) VALUES ("
            f"{_literal(table)}, '{operation}', {_object_id_expr(columns, row)}, "
            f"{_tenancy_expr(columns, row, 'company_id')}, "
            f"{_tenancy_expr(columns, row, 'project_id')}, "
            f"{old_data}, {new_data}, __CHANGED__, "
            f"USER(), CURRENT_USER(), CONNECTION_ID(), UTC_TIMESTAMP(6));"
        )

        if operation == "UPDATE":
            # An UPDATE that sets every column to its current value still
            # fires the trigger; only record ones that changed something.
            diff = ", ".join(
                f"IF(OLD.{_quote(n)} <=> NEW.{_quote(n)}, NULL, {_literal(n)})"
                for n, _, _ in columns
            )
            body = (
                f"DECLARE changed TEXT; "
                f"IF {APP_SESSION_VAR} IS NULL THEN "
                f"SET changed = CONCAT_WS(',', {diff}); "
                f"IF changed <> '' THEN "
                + insert.replace("__CHANGED__", "CONCAT('[\"', REPLACE(changed, ',', '\",\"'), '\"]')")
                + " END IF; END IF;"
            )
        else:
            body = f"IF {APP_SESSION_VAR} IS NULL THEN " + insert.replace("__CHANGED__", "NULL") + " END IF;"

        statements.append(
            f"CREATE TRIGGER {_quote(_trigger_name(table, suffix))} "
            f"AFTER {operation} ON {_quote(table)} FOR EACH ROW BEGIN {body} END"
        )
    return statements


def _audited_tables(cursor):
    cursor.execute(
        "SELECT c.table_name, c.column_name, c.data_type, c.column_key "
        "FROM information_schema.columns c "
        "JOIN information_schema.tables t "
        "  ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
        "WHERE c.table_schema = DATABASE() AND t.table_type = 'BASE TABLE' "
        "ORDER BY c.table_name, c.ordinal_position"
    )
    tables = {}
    for table, column, data_type, key in cursor.fetchall():
        if table in EXCLUDED_TABLES:
            continue
        tables.setdefault(table, []).append((column, data_type.lower(), key))
    return tables


def drop_triggers(using="default"):
    """Drop every DB Change Audit trigger. Returns how many were dropped."""
    connection = connections[using]
    if connection.vendor != "mysql":
        return 0
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT trigger_name FROM information_schema.triggers "
            "WHERE trigger_schema = DATABASE() AND trigger_name LIKE %s",
            [TRIGGER_PREFIX.replace("_", "\\_") + "%"],
        )
        names = [row[0] for row in cursor.fetchall()]
        for name in names:
            cursor.execute(f"DROP TRIGGER IF EXISTS {_quote(name)}")
    return len(names)


def install_triggers(using="default"):
    """(Re)build the triggers on every table from the current schema.
    Returns the number of tables now audited."""
    connection = connections[using]
    if not is_enabled(connection):
        return 0
    with connection.cursor() as cursor:
        if AUDIT_TABLE not in connection.introspection.table_names(cursor):
            # migrate hasn't created the audit table yet.
            return 0
        drop_triggers(using)
        tables = _audited_tables(cursor)
        for table, columns in tables.items():
            for statement in build_trigger_sql(table, columns):
                cursor.execute(statement)
    return len(tables)


def drop_triggers_before_migrate(sender, using="default", **kwargs):
    try:
        drop_triggers(using)
    except Exception:
        logger.exception("Could not drop DB change audit triggers before migrate")


def install_triggers_after_migrate(sender, using="default", **kwargs):
    try:
        install_triggers(using)
    except Exception:
        # Most likely the DB account lacks the TRIGGER privilege (or, with
        # binary logging on, SUPER / log_bin_trust_function_creators).
        logger.exception("Could not install DB change audit triggers after migrate")
