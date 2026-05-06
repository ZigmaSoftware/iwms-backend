from django.db import models
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

def generate_supervisor_zone_access_audit_id():
    return f"SZAA-{generate_unique_id()}"

class SupervisorZoneAccessAudit(models.Model):
    # -----------------------------
    # SYSTEM IDENTITY
    # -----------------------------
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_supervisor_zone_access_audit_id,
        editable=False,
    )

    # -----------------------------
    # ACTOR & SUBJECT
    # -----------------------------
    supervisor = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="zone_access_audits",
        to_field="staff_unique_id",
        db_column="supervisor_id"
    )

    performed_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="performed_zone_access_audits",
        to_field="staff_unique_id",
        db_column="performed_by",
        null=True,
        blank=True
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="supervisor_zone_access_audits",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="supervisor_zone_access_audits",
        db_column="project_id",
    )

    # -----------------------------
    # BEFORE / AFTER STATE
    # -----------------------------
    old_zone_ids = models.JSONField(
        null=True,
        blank=True,
        help_text="Zones before change"
    )

    new_zone_ids = models.JSONField(
        null=False,
        help_text="Zones after change"
    )

    # -----------------------------
    # GOVERNANCE
    # -----------------------------
    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
    )

    performed_role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default="ADMIN"
    )

    remarks = models.TextField(null=True, blank=True)

    # -----------------------------
    # AUDIT TIMESTAMP
    # -----------------------------
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["supervisor"]),
            models.Index(fields=["performed_by"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Supervisor {self.supervisor_id} zone access change"
