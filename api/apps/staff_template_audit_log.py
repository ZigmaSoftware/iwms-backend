from django.db import models

from .userCreation import User


class StaffTemplateAuditLog(models.Model):
    class EntityType(models.TextChoices):
        STAFF_TEMPLATE = "STAFF_TEMPLATE", "Staff Template"
        ALTERNATIVE_TEMPLATE = "ALTERNATIVE_TEMPLATE", "Alternative Template"

    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        APPROVE = "APPROVE", "Approve"
        APPLY = "APPLY", "Apply"
        CANCEL = "CANCEL", "Cancel"

    class PerformedRole(models.TextChoices):
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        ADMIN = "ADMIN", "Admin"
        SYSTEM = "SYSTEM", "System"

    entity_type = models.CharField(
        max_length=30,
        choices=EntityType.choices,
        help_text="STAFF_TEMPLATE or ALTERNATIVE_TEMPLATE",
    )
    entity_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="StaffTemplate.unique_id or AlternativeStaffTemplate.unique_id",
    )

    action = models.CharField(
        max_length=20,
        choices=Action.choices,
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="staff_template_audit_logs",
        db_column="performed_by",
        to_field="unique_id",
    )
    performed_role = models.CharField(
        max_length=20,
        choices=PerformedRole.choices,
    )

    change_remarks = models.TextField(
        null=True,
        blank=True,
    )
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_template_audit_log"
        ordering = ["-performed_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["performed_by"]),
            models.Index(fields=["performed_at"]),
        ]

    def __str__(self):
        return f"{self.entity_type} | {self.entity_id} | {self.action}"
