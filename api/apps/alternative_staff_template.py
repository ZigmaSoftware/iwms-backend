import uuid
from django.db import models
from django.conf import settings


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
    id = models.BigAutoField(primary_key=True)

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
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='driver_id',
        related_name='alt_driver_templates'
    )

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='operator_id',
        related_name='alt_operator_templates'
    )

    extra_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='extra_operator_id',
        related_name='alt_extra_operator_templates',
        null=True,
        blank=True
    )

    # ---- Change Justification ----
    change_reason = models.CharField(max_length=100)
    change_remarks = models.TextField(null=True, blank=True)

    # ---- Approval Workflow ----
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='requested_by',
        related_name='alt_staff_requested'
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='approved_by',
        related_name='alt_staff_approved'
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
