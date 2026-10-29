from django.db import models


class DbChangeAudit(models.Model):
    """One row per INSERT/UPDATE/DELETE made on the database directly — from
    a SQL client, a script, phpMyAdmin — rather than through this app.

    Written only by the MySQL/MariaDB triggers installed by
    app.services.db_change_audit; Django never creates or edits these rows.
    Writes made through Django are skipped by the triggers (the app marks its
    own connections, see mark_app_connection), so app changes stay in
    CommonAudit and are not logged twice.
    """

    OPERATION_INSERT = "INSERT"
    OPERATION_UPDATE = "UPDATE"
    OPERATION_DELETE = "DELETE"

    OPERATION_CHOICES = [
        (OPERATION_INSERT, "Created"),
        (OPERATION_UPDATE, "Updated"),
        (OPERATION_DELETE, "Deleted"),
    ]

    table_name = models.CharField(max_length=64, db_index=True)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES, db_index=True)
    # The row's unique_id when the table has one, otherwise its primary key.
    object_id = models.CharField(max_length=150, null=True, blank=True, db_index=True)

    # Copied from the changed row when its table carries tenancy columns, so
    # a company user only sees their own company's changes.
    company_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    project_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Full row before/after the change; old_data is null for an INSERT and
    # new_data for a DELETE. changed_columns lists what an UPDATE changed.
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    changed_columns = models.JSONField(null=True, blank=True)

    # Who made the change, as the database saw it: USER() is the login and
    # client host ("root@192.168.1.20"), CURRENT_USER() the matched account.
    db_user = models.CharField(max_length=150, null=True, blank=True, db_index=True)
    db_account = models.CharField(max_length=150, null=True, blank=True)
    connection_id = models.BigIntegerField(null=True, blank=True)

    changed_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "db_change_audit"
        ordering = ["-changed_at", "-id"]
        indexes = [
            models.Index(fields=["company_id", "-changed_at"]),
            models.Index(fields=["table_name", "-changed_at"]),
        ]

    def __str__(self):
        return f"{self.operation} {self.table_name} {self.object_id}"
