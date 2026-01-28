from django.db import models
from django.db.models import Max
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
    unique_id = models.CharField(
        max_length=50,
        unique=True,
        default=generate_alternative_staff_template_id,
        editable=False
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
        on_delete=models.PROTECT,
        db_column="driver_id",
        to_field="unique_id",
        related_name='alt_driver_templates'
    )

    operator_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
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

    # ---- HUMAN READABLE BUSINESS CODE ----
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Human-friendly identifier (e.g. RAVI-KART-01-ALT-01)"
    )

    # ---- Audit ----
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'api_alternative_staff_template'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['staff_template', 'effective_date']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['display_code']),
        ]

    # ------------------------------------------------------------------
    # DISPLAY CODE GENERATION
    # ------------------------------------------------------------------
    def _generate_display_code(self):
        """
        Format: <PARENT_DISPLAY_CODE>-ALT-<SEQ>
        Example: RAVI-KART-01-ALT-01
        
        This creates a clear hierarchy showing:
        - Which staff template this is an alternative for
        - Sequential numbering for multiple alternatives
        """
        if not self.staff_template:
            return f"UNKNOWN-ALT-{self.pk or '00'}"

        parent_code = getattr(self.staff_template, 'display_code', None)
        if not parent_code:
            parent_code = f"TPL-{self.staff_template.pk}"

        base_code = f"{parent_code}-ALT"

        # Find highest existing sequence for this parent template
        last_code = (
            AlternativeStaffTemplate.objects
            .filter(display_code__startswith=base_code)
            .aggregate(max_code=Max("display_code"))
            .get("max_code")
        )

        if last_code:
            try:
                last_seq = int(last_code.split("-")[-1])
            except (ValueError, IndexError):
                last_seq = 0
        else:
            last_seq = 0

        next_seq = last_seq + 1
        return f"{base_code}-{next_seq:02d}"

    # ------------------------------------------------------------------
    # OVERRIDE SAVE
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.display_code:
            self.display_code = self._generate_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_code