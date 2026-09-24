from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


# ------------------------------------------------------------------
# SYSTEM UNIQUE ID (Machine-readable)
# ------------------------------------------------------------------
def generate_stafftemplate_id():
    return f"STFTEMP-{generate_unique_id(length=6)}"

class StaffTemplate(BaseMaster):
    
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"


    unique_id = models.CharField(
        max_length=20,
        primary_key=True,
        default=generate_stafftemplate_id,
        editable=False
    )

    # ---------------- DRIVER ROLE ----------------
    driver_id = models.CharField(max_length=30, null=True, blank=True)

    # ---------------- OPERATOR ROLE ----------------
    operator_id = models.CharField(max_length=30, null=True, blank=True)
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        help_text="List of additional operator unique IDs"
    )

    # ---------------- HUMAN READABLE BUSINESS CODE ----------------
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Supervisor friendly identifier (e.g. RAVI-KART-01)"
    )

    # ---------------- STATUS ----------------
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    
    CASCADE_SOFT_DELETE = ("trip_plans", "daily_trip_assignments", "daily_trip_logs")
    CACHE_SCOPES = ("staff_template_list", "staff_template_detail")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------------- META ----------------
    class Meta:
        indexes = [
            models.Index(fields=["display_code"]),
        ]
        ordering = ["-created_at"]

    # ------------------------------------------------------------------
    # DISPLAY CODE GENERATION (Enterprise Safe)
    # ------------------------------------------------------------------
    def _generate_display_code(self):
        """
        Format: <DRIVER>-<OPERATOR>-<SEQ>
        Example: RAVI-KART-01
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

        base_code = f"{driver_name}-{operator_name}"

        # Find highest existing sequence
        last_code = (
            StaffTemplate.objects
            .filter(display_code__startswith=base_code)
            .aggregate(max_code=Max("display_code"))
            .get("max_code")
        )

        if last_code:
            try:
                last_seq = int(last_code.split("-")[-1])
            except ValueError:
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
