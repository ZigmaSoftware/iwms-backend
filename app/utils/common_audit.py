from django.db import models
from django.utils import timezone
from app.utils.comfun import generate_unique_id


def generate_audit_id():
    return f"AUDIT-{generate_unique_id()}"


class CommonAudit(models.Model):

    class Scope(models.TextChoices):
        # Acted on by a platform super admin, who belongs to no company and
        # no project. Kept as an explicit scope rather than "company_id is
        # null" so enterprise listing can filter for it directly.
        PLATFORM = "platform", "Platform"
        # Acted on within a company but not tied to one project (project_id
        # is null on the record that changed).
        COMPANY = "company", "Company"
        # Acted on inside a single project.
        PROJECT = "project", "Project"

    uuid = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_audit_id,
        editable=False
    )

    module_name = models.CharField(max_length=150)
    endpoint_name = models.CharField(max_length=150)
    method = models.CharField(max_length=10)  

    previous_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)

    object_id = models.CharField(max_length=150, null=True, blank=True)

    # ── Tenancy ──────────────────────────────────────────────────────────
    # Denormalized to plain CharFields rather than FKs: an audit row must
    # survive its company/project being deleted, and must never block that
    # delete with a PROTECT constraint. Names are snapshots taken at write
    # time so the trail still reads correctly after a later rename.
    scope = models.CharField(
        max_length=20,
        choices=Scope.choices,
        default=Scope.PLATFORM,
        db_index=True,
    )
    company_unique_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=150, null=True, blank=True)
    project_unique_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    project_name = models.CharField(max_length=150, null=True, blank=True)

    # ── Actor ────────────────────────────────────────────────────────────
    # createdBy stays as-is (existing rows depend on it and it is a
    # documented search field); the id/name pair is added alongside it.
    createdBy = models.CharField(max_length=150, null=True, blank=True)
    created_by_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    created_by_name = models.CharField(max_length=200, null=True, blank=True)
    created_by_type = models.CharField(max_length=50, null=True, blank=True)

    createdAt = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "common_audit"
        ordering = ["-createdAt"]
        indexes = [
            models.Index(fields=["company_unique_id", "project_unique_id", "-createdAt"]),
            models.Index(fields=["module_name", "-createdAt"]),
        ]

    def __str__(self):
        return self.uuid
