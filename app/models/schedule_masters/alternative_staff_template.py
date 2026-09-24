from django.db import models
from django.db.models import Max
from app.utils.comfun import generate_unique_id
from app.utils.base_models import BaseMaster


def generate_alternative_staff_template_id():
    return f"ALTSTAFFTEMPLATE-{generate_unique_id()}"


class AlternativeStaffTemplate(BaseMaster):
    """
    Tracks temporary or permanent staff substitutions against
    a staff template with approval workflow and audit trail.
    """

    APPROVAL_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    # ------------------------------------------------------------------
    # CORE IDENTIFIER
    # ------------------------------------------------------------------

    unique_id = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_alternative_staff_template_id,
        editable=False
    )

    # ------------------------------------------------------------------
    # BUSINESS RELATIONSHIPS
    # ------------------------------------------------------------------

    staff_template_id = models.CharField(max_length=20, null=True, blank=True)

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    from_date = models.DateField(null=True, blank=True)
    to_date = models.DateField(null=True, blank=True)


    # ------------------------------------------------------------------
    # STAFF ASSIGNMENT
    # ------------------------------------------------------------------

    driver_id = models.CharField(max_length=30, null=True, blank=True)

    operator_id = models.CharField(max_length=30, null=True, blank=True)

    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        null=True,
        db_column='extra_operator_id',
        help_text="List of extra operator IDs"
    )

    # ------------------------------------------------------------------
    # CHANGE JUSTIFICATION
    # ------------------------------------------------------------------

    change_reason = models.CharField(max_length=100)

    change_remarks = models.TextField(
        null=True,
        blank=True
    )

    # ------------------------------------------------------------------
    # APPROVAL WORKFLOW
    # ------------------------------------------------------------------

    approved_by = models.CharField(max_length=30, null=True, blank=True)

    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS_CHOICES,
        default='PENDING'
    )

    # ------------------------------------------------------------------
    # HUMAN READABLE CODE
    # ------------------------------------------------------------------

    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Example: RAVI-KART-01-ALT-01"
    )

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)

    # ------------------------------------------------------------------
    # META CONFIGURATION
    # ------------------------------------------------------------------

    class Meta:
        ordering = ['-created_at']

        indexes = [
            models.Index(fields=['staff_template_id']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['display_code']),
        ]

        # No longer unique per staff_template: a staff_template can accumulate
        # multiple historical AlternativeStaffTemplate rows over time (e.g. one
        # per vehicle-breakdown event). Overlapping-date-range validation for
        # the schedule-setup UI is enforced in AlternativeStaffTemplateSerializer
        # instead of at the DB level.

    # ------------------------------------------------------------------
    # DISPLAY CODE GENERATION
    # ------------------------------------------------------------------

    def _generate_display_code(self):
        """
        Format:
        <DRIVER>-<OPERATOR>-<TEMPLATE_SEQ>-ALT-<ALT_SEQ>

        Example:
        VIKR-NAVE-01-ALT-01
        """

        def resolve_staff_name(staff_id, fallback):
            if not staff_id:
                return fallback
            from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
            staff = StaffcreationOfficeDetails.objects.filter(staff_unique_id=staff_id).first()
            if staff and staff.employee_name:
                return staff.employee_name
            return fallback

        driver_name = resolve_staff_name(self.driver_id, "DRV")[:4].upper()
        operator_name = resolve_staff_name(self.operator_id, "OPR")[:4].upper()
        staff_base = f"{driver_name}-{operator_name}"

        matching_alt_templates = AlternativeStaffTemplate.objects.filter(
            display_code__startswith=f"{staff_base}-"
        )
        if self.pk:
            matching_alt_templates = matching_alt_templates.exclude(pk=self.pk)

        matching_alt_codes = matching_alt_templates.values_list(
            "display_code",
            flat=True,
        )

        existing_base_codes = []
        if self.staff_template_id:
            from app.models.schedule_masters.staff_template import StaffTemplate
            existing_base_codes.extend(
                StaffTemplate.objects
                .filter(display_code__startswith=f"{staff_base}-")
                .values_list("display_code", flat=True)
            )

        for code in matching_alt_codes:
            parts = str(code).split("-")
            if len(parts) >= 3:
                existing_base_codes.append("-".join(parts[:3]))

        base_seq = 0
        for code in existing_base_codes:
            parts = str(code).split("-")
            if len(parts) < 3:
                continue
            try:
                base_seq = max(base_seq, int(parts[2]))
            except ValueError:
                continue

        if base_seq == 0:
            base_seq = 1

        base_code = f"{staff_base}-{base_seq:02d}-ALT"

        matching_base_templates = AlternativeStaffTemplate.objects.filter(
            display_code__startswith=base_code
        )
        if self.pk:
            matching_base_templates = matching_base_templates.exclude(pk=self.pk)

        last_code = matching_base_templates.aggregate(
            max_code=Max("display_code")
        ).get("max_code")

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
    # SAVE OVERRIDE
    # ------------------------------------------------------------------

    def _staff_assignment_changed(self):
        if not self.pk:
            return False

        try:
            prev = (
                AlternativeStaffTemplate.objects
                .only("driver_id", "operator_id", "staff_template_id")
                .get(pk=self.pk)
            )
        except AlternativeStaffTemplate.DoesNotExist:
            return False

        return (
            prev.driver_id != self.driver_id
            or prev.operator_id != self.operator_id
            or prev.staff_template_id != self.staff_template_id
        )

    def save(self, *args, **kwargs):

        if not self.display_code or self._staff_assignment_changed():
            self.display_code = self._generate_display_code()

        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # STRING REPRESENTATION
    # ------------------------------------------------------------------

    def __str__(self):
        return self.display_code

    @property
    def company(self):
        from app.models.superadmin_masters.company import Company
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None

    @property
    def project(self):
        from app.models.superadmin_masters.project import Project
        if self.project_id:
            return Project.objects.filter(unique_id=self.project_id).first()
        return None

    @property
    def staff_template(self):
        from app.models.schedule_masters.staff_template import StaffTemplate
        if self.staff_template_id:
            return StaffTemplate.objects.filter(unique_id=self.staff_template_id).first()
        return None

    @property
    def driver(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.driver_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.driver_id).first()
        return None

    @property
    def operator(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.operator_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.operator_id).first()
        return None

    @property
    def approved_by_user(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.approved_by:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.approved_by).first()
        return None