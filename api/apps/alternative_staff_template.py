import uuid
from django.db import models
from .utils.comfun import generate_unique_id
from .userCreation import User


def generate_alternative_staff_template_id():
    return f"ALTSTAFFTEMPLATE-{generate_unique_id()}"


class AlternativeStaffTemplate(models.Model):
    """
    Purpose:
    Tracks temporary or permanent staff substitutions against a staff template
    with approval workflow and audit trail.
    """

    APPROVAL_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    # ---- Core Identifiers ----
    unique_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    # ---- Business Mapping ----
    staff_template = models.ForeignKey(
        'api.StaffTemplate',
        on_delete=models.PROTECT,
        db_column='staff_template_id',
        related_name='alternative_templates'
    )

    effective_date = models.DateField()

    # ---- Staff Assignment ----
    driver_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  # FIXED
        db_column="driver_id",
        to_field="unique_id",
        related_name='alt_driver_templates'
    )

    operator_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  # FIXED
        db_column="operator_id",
        to_field="unique_id",
        related_name='alt_operator_templates'
    )

    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        null=True,
        db_column='extra_operator_id',
        help_text="List of extra operator IDs"
    )

    # ---- Change Justification ----
    change_reason = models.CharField(max_length=100)
    change_remarks = models.TextField(null=True, blank=True)

    # ---- Approval Workflow ----
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column='requested_by',
        related_name='alt_staff_requested'
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column='approved_by',
        related_name='alt_staff_approved',
        null=True,
        blank=True
    )

    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS_CHOICES,
        default='PENDING'
    )

    # ---- Audit ----
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'api_alternative_staff_template'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['staff_template', 'effective_date']),
            models.Index(fields=['approval_status']),
        ]

    def __str__(self):
        return f"{self.unique_id} | {self.staff_template_id} | {self.approval_status}"
