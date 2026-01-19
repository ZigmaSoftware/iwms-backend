from django.db import models
from .utils.comfun import generate_unique_id
from .userCreation import User

def generate_stafftemplate_id():
    return f"STAFFTEMPLATE-{generate_unique_id()}"


class StaffTemplate(models.Model):
    unique_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_stafftemplate_id,
        editable=False
    )

    # ---- DRIVER ROLES ----
    driver_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="driver_templates",
        db_column="driver_id",
        to_field="unique_id"
    )

    # ---- OPERATOR ROLES ----
    operator_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="operator_templates",
        db_column="operator_id",
        to_field="unique_id"
    )
    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        help_text="List of additional operator unique IDs"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="Stafftemplate_created",
        db_column="created_by",
        to_field="unique_id"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="Stafftemplate_updated",
        db_column="updated_by",
        to_field="unique_id"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="Stafftemplate_approved",
        db_column="approved_by",
        to_field="unique_id",
        null=True,
        blank=True
    )

    STATUS_CHOICES =(
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    )
    APPROVAL_STATUS_CHOICES =(
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="INACTIVE"
    )
    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS_CHOICES,
        default="PENDING"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_staff_template"
        indexes = [
            models.Index(fields=["status", "approval_status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        
        return self.unique_id