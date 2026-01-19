from django.db import models
from api.apps.userCreation import User
from .utils.comfun import generate_unique_id

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
        User,
        on_delete=models.PROTECT,
        related_name="zone_access_audits",
        to_field="unique_id",
        db_column="supervisor_id"
    )

    performed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="performed_zone_access_audits",
        to_field="unique_id",
        db_column="performed_by"
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
        db_table = "api_supervisor_zone_access_audit"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["supervisor"]),
            models.Index(fields=["performed_by"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Supervisor {self.supervisor_id} zone access change"
