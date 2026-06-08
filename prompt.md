Execute this new plan schema for iwms backend.
You have to aligne the iwms-frontend with this new chaanges as well.,
Create seeder as well
Use this credentials for final tesitng:
he is the super admin.
username: Sathya
PASS: Sathya@123
Use this credenials and test the new changes. 
remove the trip definition and routeplan in both frontend and backend

python# ============================================================
# 1. stafftemplate.py
# ============================================================
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_stafftemplate_id():
    return f"STFTEMP-{generate_unique_id(length=6)}"


class StaffTemplate(BaseMaster):

    class ApprovalStatus(models.TextChoices):
        PENDING  = "PENDING",  "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Status(models.TextChoices):
        ACTIVE   = "ACTIVE",   "Active"
        INACTIVE = "INACTIVE", "Inactive"

    unique_id = models.CharField(
        max_length=20,
        primary_key=True,
        default=generate_stafftemplate_id,
        editable=False,
    )
    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="driver_templates",
        db_column="driver_id",
        to_field="staff_unique_id",
    )
    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="operator_templates",
        db_column="operator_id",
        to_field="staff_unique_id",
    )
    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        help_text="List of additional operator staff_unique_ids",
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="staff_templates",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="staff_templates",
        db_column="project_id",
    )
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="e.g. RAVI-KART-01",
    )
    approved_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="stafftemplate_approved",
        db_column="approved_by",
        to_field="staff_unique_id",
        null=True,
        blank=True,
    )
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "approval_status"]),
            models.Index(fields=["display_code"]),
        ]

    def _generate_display_code(self):
        def short_name(staff, fallback):
            name = getattr(staff, "employee_name", None)
            return name[:4].upper() if name else fallback

        base = (
            f"{short_name(self.driver_id, 'DRV')}-"
            f"{short_name(self.operator_id, 'OPR')}"
        )
        last = (
            StaffTemplate.objects
            .filter(display_code__startswith=base)
            .aggregate(max_code=Max("display_code"))
            .get("max_code")
        )
        seq = 0
        if last:
            try:
                seq = int(last.split("-")[-1])
            except ValueError:
                pass
        return f"{base}-{seq + 1:02d}"

    def save(self, *args, **kwargs):
        if not self.display_code:
            self.display_code = self._generate_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_code
python# ============================================================
# 2. alternative_staff_template.py
# ============================================================
from django.db import models
from django.db.models import Max
from app.utils.comfun import generate_unique_id
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_alternative_staff_template_id():
    return f"ALTSTAFFTEMPLATE-{generate_unique_id()}"


class AlternativeStaffTemplate(models.Model):

    APPROVAL_STATUS_CHOICES = (
        ("PENDING",  "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    unique_id = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_alternative_staff_template_id,
        editable=False,
    )
    staff_template = models.ForeignKey(
        "app.StaffTemplate",
        on_delete=models.PROTECT,
        db_column="staff_template_id",
        related_name="alternative_templates",
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="alternative_staff_templates",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="alternative_staff_templates",
        db_column="project_id",
    )
    from_date = models.DateField(null=True, blank=True)
    to_date   = models.DateField(null=True, blank=True)

    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="driver_id",
        to_field="staff_unique_id",
        related_name="alt_driver_templates",
    )
    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="operator_id",
        to_field="staff_unique_id",
        related_name="alt_operator_templates",
    )
    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        null=True,
        db_column="extra_operator_id",
    )
    change_reason  = models.CharField(max_length=100)
    change_remarks = models.TextField(null=True, blank=True)

    approved_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="approved_by",
        related_name="alt_staff_approved",
        null=True,
        blank=True,
    )
    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS_CHOICES,
        default="PENDING",
    )
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="e.g. RAVI-KART-01-ALT-01",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["staff_template"]),
            models.Index(fields=["approval_status"]),
            models.Index(fields=["display_code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["staff_template", "from_date"],
                name="unique_alt_template_per_staff_and_date",
            )
        ]

    def _generate_display_code(self):
        def short_name(staff, fallback):
            name = getattr(staff, "employee_name", None)
            return name[:4].upper() if name else fallback

        driver_name   = short_name(self.driver_id, "DRV")
        operator_name = short_name(self.operator_id, "OPR")
        staff_base    = f"{driver_name}-{operator_name}"

        existing = []
        if self.staff_template:
            from app.models.user_creations.stafftemplate import StaffTemplate
            existing += list(
                StaffTemplate.objects
                .filter(display_code__startswith=f"{staff_base}-")
                .values_list("display_code", flat=True)
            )
        sibling_qs = AlternativeStaffTemplate.objects.filter(
            display_code__startswith=f"{staff_base}-"
        )
        if self.pk:
            sibling_qs = sibling_qs.exclude(pk=self.pk)
        for code in sibling_qs.values_list("display_code", flat=True):
            parts = str(code).split("-")
            if len(parts) >= 3:
                existing.append("-".join(parts[:3]))

        base_seq = max(
            (int(str(c).split("-")[2]) for c in existing
             if len(str(c).split("-")) >= 3
             and str(c).split("-")[2].isdigit()),
            default=1,
        )

        base_code = f"{staff_base}-{base_seq:02d}-ALT"
        qs = AlternativeStaffTemplate.objects.filter(
            display_code__startswith=base_code
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        last = qs.aggregate(max_code=Max("display_code")).get("max_code")
        last_seq = 0
        if last:
            try:
                last_seq = int(last.split("-")[-1])
            except (ValueError, IndexError):
                pass
        return f"{base_code}-{last_seq + 1:02d}"

    def _staff_assignment_changed(self):
        if not self.pk:
            return False
        try:
            prev = AlternativeStaffTemplate.objects.only(
                "driver_id", "operator_id", "staff_template"
            ).get(pk=self.pk)
        except AlternativeStaffTemplate.DoesNotExist:
            return False
        return (
            prev.driver_id_id        != self.driver_id_id
            or prev.operator_id_id   != self.operator_id_id
            or prev.staff_template_id != self.staff_template_id
        )

    def save(self, *args, **kwargs):
        if not self.display_code or self._staff_assignment_changed():
            self.display_code = self._generate_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_code
python# ============================================================
# 3. collection_point.py
# ============================================================
from django.db import models
from django.core.exceptions import ValidationError
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.panchayat import Panchayat
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.common_masters.state import State


def generate_collection_point_id():
    return f"CP-{generate_unique_id()}"


class Collection_point(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_collection_point_id,
        editable=False,
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="project_id",
    )
    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="state_id",
    )
    city_id = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="city_id",
    )
    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="district_id",
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="panchayat_id",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="ward_id",
        null=True,
        blank=True,
    )
    cp_name   = models.CharField(max_length=100)
    latitude  = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if not self.panchayat_id and not self.ward_id:
            raise ValidationError(
                "Collection Point must belong to either a Ward or a Panchayat."
            )
        if self.panchayat_id and self.ward_id:
            raise ValidationError(
                "Collection Point cannot belong to both Ward and Panchayat."
            )

    def __str__(self):
        if self.panchayat_id:
            return f"{self.cp_name} (Panchayat: {self.panchayat_id.panchayat_name})"
        if self.ward_id:
            return f"{self.cp_name} (Ward: {self.ward_id.ward_name})"
        return self.cp_name
python# ============================================================
# 4. trip_plan.py
# ============================================================
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_trip_plan_id():
    return f"TPLAN-{generate_unique_id()}"


class TripPlan(BaseMaster):
    """
    Master blueprint for a route.
    One TripPlan → many DailyTripAssignments (one per day).
    Collection points for the route live in TripPlanCollectionPoint.
    """

    class ApprovalStatus(models.TextChoices):
        PENDING  = "PENDING",  "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Status(models.TextChoices):
        ACTIVE   = "ACTIVE",   "Active"
        INACTIVE = "INACTIVE", "Inactive"

    # ---- identifier ------------------------------------------------
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_trip_plan_id,
        editable=False,
    )
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="e.g. RAVI-TN01AB1234-01",
    )

    # ---- tenancy ---------------------------------------------------
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="trip_plans",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="trip_plans",
        db_column="project_id",
    )

    # ---- WHERE -----------------------------------------------------
    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
    )
    city_id = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
    )
    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        null=True,
        blank=True,
    )
    # panchayat XOR ward — mirrors Collection_point constraint
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        null=True,
        blank=True,
    )

    # ---- WHO -------------------------------------------------------
    staff_template_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="staff_template_id",
    )
    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
    )
    supervisor_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        related_name="trip_plans",
    )

    # ---- WHAT ------------------------------------------------------
    property_id = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="property_id",
    )
    sub_property_id = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="sub_property_id",
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="waste_type_id",
    )
    trip_trigger_weight_kg = models.PositiveIntegerField(
        help_text="Collected weight (kg) that triggers a trip dispatch.",
    )
    max_vehicle_capacity_kg = models.PositiveIntegerField(
        help_text="Hard ceiling for vehicle load (kg).",
    )

    # ---- WHEN (default schedule) -----------------------------------
    scheduled_time = models.TimeField(
        help_text="Default departure time for trips auto-generated from this plan.",
    )

    # ---- workflow --------------------------------------------------
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "approval_status"]),
            models.Index(fields=["display_code"]),
            models.Index(fields=["district_id", "city_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(panchayat_id__isnull=False, ward_id__isnull=True) |
                    models.Q(panchayat_id__isnull=True,  ward_id__isnull=False)
                ),
                name="trip_plan_panchayat_xor_ward",
            )
        ]

    def _generate_display_code(self):
        driver_name = "DRV"
        if self.staff_template_id and self.staff_template_id.driver_id:
            driver_name = (
                self.staff_template_id.driver_id.employee_name[:6]
                .upper().replace(" ", "")
            )
        vehicle_no = "VEH"
        if self.vehicle_id:
            vehicle_no = self.vehicle_id.vehicle_no.upper().replace(" ", "")

        base = f"{driver_name}-{vehicle_no}"
        last = (
            TripPlan.objects
            .filter(display_code__startswith=base)
            .aggregate(max_code=Max("display_code"))
            .get("max_code")
        )
        seq = 0
        if last:
            try:
                seq = int(last.split("-")[-1])
            except ValueError:
                pass
        return f"{base}-{seq + 1:02d}"

    def save(self, *args, **kwargs):
        if not self.display_code:
            self.display_code = self._generate_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_code or self.unique_id
python# ============================================================
# 5. trip_plan_collection_point.py  ← NEW
# ============================================================
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.transport_masters.trip_plan import TripPlan
from app.models.assets.collection_point import Collection_point
from app.models.assets.bins import Bins


def generate_tpcp_id():
    return f"TPCP-{generate_unique_id()}"


class TripPlanCollectionPoint(BaseMaster):
    """
    Master stop list for a TripPlan.

    Each row = one bin at one collection point that the vehicle
    must visit on EVERY trip generated from this plan.

    When a DailyTripAssignment is created (manually or via the
    nightly scheduler), a post_save signal reads these rows and
    copies them into DailyTripCollectionPoint automatically —
    one row per active TripPlanCollectionPoint, preserving sequence.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_tpcp_id,
        editable=False,
    )
    trip_plan_id = models.ForeignKey(
        TripPlan,
        on_delete=models.CASCADE,
        to_field="unique_id",
        related_name="plan_collection_points",
        db_column="trip_plan_id",
    )
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plan_cps",
        db_column="collection_point_id",
    )
    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plan_cps",
        db_column="bin_id",
    )
    sequence = models.PositiveIntegerField(
        help_text="Visit order within the route.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive stops are skipped during auto-assignment.",
    )

    class Meta:
        ordering = ["trip_plan_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_plan_id", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_plan_id", "collection_point_id"],
                name="uniq_cp_per_trip_plan",
            ),
            models.UniqueConstraint(
                fields=["trip_plan_id", "sequence"],
                name="uniq_sequence_per_trip_plan",
            ),
        ]

    def __str__(self):
        return (
            f"{self.trip_plan_id_id} → "
            f"{self.collection_point_id_id} (seq {self.sequence})"
        )
python# ============================================================
# 6. daily_trip_assignment.py
# ============================================================
from django.db import models
from django.utils import timezone
from app.utils.base_models import BaseMaster
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.user_creations.waste_collection_bluetooth import WasteType


def _generate_trip_assignment_unique_id(company_id, project_id):
    today  = timezone.localdate()
    prefix = f"TRIP-{today.year}-{today.month:02d}"
    count  = DailyTripAssignment.objects.filter(
        company_id=company_id,
        project_id=project_id,
        unique_id__startswith=f"{prefix}-",
    ).count()
    return f"{prefix}-{count + 1:03d}"


class DailyTripAssignment(BaseMaster):

    STATUS_SCHEDULED   = "Scheduled"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED   = "Completed"
    STATUS_CANCELLED   = "Cancelled"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED,   "Scheduled"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED,   "Completed"),
        (STATUS_CANCELLED,   "Cancelled"),
    ]

    APPROVAL_PENDING  = "Pending"
    APPROVAL_APPROVED = "Approved"
    APPROVAL_REJECTED = "Rejected"

    APPROVAL_CHOICES = [
        (APPROVAL_PENDING,  "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    # ---- identifier ------------------------------------------------
    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    # ---- tenancy ---------------------------------------------------
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="daily_trip_assignments",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        related_name="daily_trip_assignments",
    )

    # ---- plan ------------------------------------------------------
    trip_plan_id = models.ForeignKey(
        TripPlan,
        on_delete=models.PROTECT,
        db_column="trip_plan_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    # ---- staff -----------------------------------------------------
    staff_template_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        db_column="staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )
    alt_staff_template_id = models.ForeignKey(
        AlternativeStaffTemplate,
        on_delete=models.PROTECT,
        db_column="alt_staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ---- location --------------------------------------------------
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        db_column="ward_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ---- waste -----------------------------------------------------
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    # ---- vehicle (overrides trip_plan default when set) ------------
    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ---- scheduling ------------------------------------------------
    trip_date         = models.DateField()
    scheduled_time    = models.TimeField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time   = models.TimeField(null=True, blank=True)

    # ---- workflow --------------------------------------------------
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        db_index=True,
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_PENDING,
        db_index=True,
    )
    remarks = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-trip_date", "-scheduled_time"]
        indexes = [
            models.Index(fields=["trip_date", "status"]),
            models.Index(fields=["trip_plan_id", "trip_date"]),
            models.Index(fields=["panchayat_id", "trip_date"]),
            models.Index(fields=["ward_id",      "trip_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(panchayat_id__isnull=False, ward_id__isnull=True) |
                    models.Q(panchayat_id__isnull=True,  ward_id__isnull=False)
                ),
                name="daily_trip_assignment_panchayat_xor_ward",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.unique_id:
            self.unique_id = _generate_trip_assignment_unique_id(
                self.company_id, self.project_id
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id

    def mark_completed_if_all_cps_collected(self):
        children = self.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return False
        if children.filter(is_collected=False).exists():
            return False
        if self.status == self.STATUS_COMPLETED:
            return True
        update_fields = ["status", "updated_at"]
        self.status = self.STATUS_COMPLETED
        if not self.actual_end_time:
            self.actual_end_time = timezone.localtime().time()
            update_fields.append("actual_end_time")
        self.save(update_fields=update_fields)
        return True
python# ============================================================
# 7. daily_trip_collection_point.py
# ============================================================
from django.db import models
from django.utils import timezone
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.assets.bins import Bins
from app.models.assets.collection_point import Collection_point
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.user_creations.staffcreation import Staffcreation


def generate_daily_trip_cp_id():
    return f"DTCP-{generate_unique_id(length=10)}"


class DailyTripCollectionPoint(BaseMaster):

    STATUS_PENDING   = "Pending"
    STATUS_COLLECTED = "Collected"
    STATUS_SKIPPED   = "Skipped"

    STATUS_CHOICES = [
        (STATUS_PENDING,   "Pending"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_SKIPPED,   "Skipped"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_daily_trip_cp_id,
        editable=False,
    )

    # ---- parent ----------------------------------------------------
    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.CASCADE,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="trip_collection_points",
    )

    # ---- stop ------------------------------------------------------
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="daily_trip_cps",
    )
    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        db_column="bin_id",
        to_field="unique_id",
        related_name="daily_trip_cps",
    )
    sequence = models.PositiveIntegerField(
        help_text="Visit order copied from TripPlanCollectionPoint.",
    )

    # ---- collection state ------------------------------------------
    is_collected        = models.BooleanField(default=False, db_index=True)
    collected_at        = models.DateTimeField(null=True, blank=True)
    collected_by        = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        db_column="collected_by",
        to_field="staff_unique_id",
        related_name="collected_trip_cps",
        null=True,
        blank=True,
    )
    collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    class Meta:
        ordering = ["trip_assignment_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "is_collected"]),
            models.Index(fields=["trip_assignment_id", "sequence"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_assignment_id", "collection_point_id"],
                name="uniq_trip_cp_per_assignment",
            ),
        ]

    def __str__(self):
        return f"{self.trip_assignment_id_id}:{self.collection_point_id_id}"

    def mark_collected(self, weight_kg, collected_by, collected_at=None):
        self.collected_weight_kg = weight_kg
        self.collected_by        = collected_by
        self.collected_at        = collected_at or timezone.now()
        self.is_collected        = True
        self.status              = self.STATUS_COLLECTED
        self.save(update_fields=[
            "collected_weight_kg",
            "collected_by",
            "collected_at",
            "is_collected",
            "status",
            "updated_at",
        ])
        self.trip_assignment_id.mark_completed_if_all_cps_collected()
python# ============================================================
# 8. bin_collection_event.py
# ============================================================
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.assets.bins import Bins
from app.models.assets.collection_point import Collection_point
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.waste_collection_bluetooth import WasteType


def generate_bin_collection_event_id():
    return f"BCE-{generate_unique_id(length=10)}"


class BinCollectionEvent(BaseMaster):
    """
    Permanent append-only audit ledger.
    One row per operator scan. Never edited after creation.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_bin_collection_event_id,
        editable=False,
    )

    # ---- tenancy ---------------------------------------------------
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="bin_collection_events",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        related_name="bin_collection_events",
    )

    # ---- trip context ----------------------------------------------
    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    trip_collection_point_id = models.OneToOneField(
        DailyTripCollectionPoint,
        on_delete=models.PROTECT,
        db_column="trip_collection_point_id",
        to_field="unique_id",
        related_name="bin_collection_event",
    )

    # ---- location --------------------------------------------------
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    # Denormalized from collection_point for fast filtering
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="bin_collection_events",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        db_column="ward_id",
        to_field="unique_id",
        related_name="bin_collection_events",
        null=True,
        blank=True,
    )

    # ---- asset -----------------------------------------------------
    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        db_column="bin_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="bin_collection_events",
        null=True,
        blank=True,
    )

    # ---- measurement -----------------------------------------------
    collected_weight_kg = models.DecimalField(max_digits=10, decimal_places=2)
    driver_latitude     = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    driver_longitude    = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes               = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "created_at"]),
            models.Index(fields=["panchayat_id",       "created_at"]),
            models.Index(fields=["ward_id",            "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(panchayat_id__isnull=False, ward_id__isnull=True) |
                    models.Q(panchayat_id__isnull=True,  ward_id__isnull=False)
                ),
                name="bin_collection_event_panchayat_xor_ward",
            )
        ]

    def save(self, *args, **kwargs):
        # Auto-derive panchayat/ward from collection_point
        if self.collection_point_id and not self.panchayat_id and not self.ward_id:
            cp = self.collection_point_id
            self.panchayat_id = cp.panchayat_id
            self.ward_id      = cp.ward_id
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id
python# ============================================================
# 9. daily_trip_log.py
# ============================================================
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from app.utils.base_models import Account, BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.assets.bins import Bins
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType


def _generate_daily_trip_log_unique_id(company_id, project_id):
    today  = timezone.localdate()
    prefix = f"DTL-{today.year}-{today.month:02d}"
    count  = DailyTripLog.objects.filter(
        company_id=company_id,
        project_id=project_id,
        unique_id__startswith=f"{prefix}-",
    ).count()
    return f"{prefix}-{count + 1:03d}"


class DailyTripLog(BaseMaster):
    """
    One summary log per DailyTripAssignment.
    Auto-created when the last bin in the trip is scanned.
    Verified by a supervisor.
    """

    LOG_STATUS_DRAFT     = "Draft"
    LOG_STATUS_SUBMITTED = "Submitted"
    LOG_STATUS_VERIFIED  = "Verified"

    LOG_STATUS_CHOICES = [
        (LOG_STATUS_DRAFT,     "Draft"),
        (LOG_STATUS_SUBMITTED, "Submitted"),
        (LOG_STATUS_VERIFIED,  "Verified"),
    ]

    # ---- identifier ------------------------------------------------
    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    # ---- parent ----------------------------------------------------
    trip_assignment_id = models.OneToOneField(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="daily_trip_log",
    )

    # ---- tenancy (denormalized) ------------------------------------
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="daily_trip_logs",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        related_name="daily_trip_logs",
    )

    # ---- location (panchayat XOR ward) -----------------------------
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        db_column="ward_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
        null=True,
        blank=True,
    )

    # ---- waste -----------------------------------------------------
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )

    # ---- timing ----------------------------------------------------
    trip_date         = models.DateField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time   = models.TimeField(null=True, blank=True)

    # ---- staff snapshot --------------------------------------------
    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="driver_id",
        to_field="staff_unique_id",
        related_name="daily_trip_logs_as_driver",
    )
    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="operator_id",
        to_field="staff_unique_id",
        related_name="daily_trip_logs_as_operator",
    )
    extra_operator_ids = models.ManyToManyField(
        Staffcreation,
        blank=True,
        related_name="daily_trip_logs_as_extra_operator",
    )

    # ---- collection summary ----------------------------------------
    collected_weight_kg = models.DecimalField(max_digits=10, decimal_places=2)
    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )
    bin_ids = models.ManyToManyField(
        Bins,
        blank=True,
        related_name="daily_trip_logs",
    )

    # ---- workflow --------------------------------------------------
    remarks    = models.TextField(null=True, blank=True)
    log_status = models.CharField(
        max_length=20,
        choices=LOG_STATUS_CHOICES,
        default=LOG_STATUS_DRAFT,
        db_index=True,
    )
    verified_by = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="verified_by",
        related_name="verified_daily_trip_logs",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-trip_date", "-created_at"]
        indexes = [
            models.Index(fields=["trip_date", "log_status"]),
            models.Index(fields=["company_id", "project_id", "trip_date"]),
            models.Index(fields=["panchayat_id", "trip_date"]),
            models.Index(fields=["ward_id",      "trip_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(panchayat_id__isnull=False, ward_id__isnull=True) |
                    models.Q(panchayat_id__isnull=True,  ward_id__isnull=False)
                ),
                name="daily_trip_log_panchayat_xor_ward",
            )
        ]

    def __str__(self):
        return self.unique_id

    def _resolve_effective_staff_template(self):
        assignment = self.trip_assignment_id
        return assignment.alt_staff_template_id or assignment.staff_template_id

    def autofill_from_assignment(self):
        assignment = self.trip_assignment_id
        if not assignment:
            return

        trip_plan = assignment.trip_plan_id

        # Tenancy
        self.company_id   = assignment.company_id
        self.project_id   = assignment.project_id

        # Location — cascade: assignment → trip_plan → first CP
        if not self.panchayat_id and not self.ward_id:
            if assignment.panchayat_id_id:
                self.panchayat_id = assignment.panchayat_id
            elif assignment.ward_id_id:
                self.ward_id = assignment.ward_id
            elif trip_plan.panchayat_id_id:
                self.panchayat_id = trip_plan.panchayat_id
            elif trip_plan.ward_id_id:
                self.ward_id = trip_plan.ward_id
            else:
                first_cp = (
                    assignment.trip_collection_points
                    .filter(is_deleted=False)
                    .select_related("collection_point_id")
                    .order_by("sequence")
                    .first()
                )
                if first_cp:
                    cp = first_cp.collection_point_id
                    self.panchayat_id = cp.panchayat_id
                    self.ward_id      = cp.ward_id

        # Waste
        self.waste_type_id = assignment.waste_type_id

        # Timing
        self.trip_date         = assignment.trip_date
        self.actual_start_time = self.actual_start_time or assignment.actual_start_time
        self.actual_end_time   = self.actual_end_time   or assignment.actual_end_time

        # Staff snapshot — alt takes priority over base
        staff_template = self._resolve_effective_staff_template()
        if staff_template:
            self.driver_id   = staff_template.driver_id
            self.operator_id = staff_template.operator_id

        # Vehicle — assignment overrides trip_plan default
        if not getattr(self, "vehicle_id_id", None):
            if getattr(assignment, "vehicle_id_id", None):
                self.vehicle_id = assignment.vehicle_id
            elif getattr(trip_plan, "vehicle_id_id", None):
                self.vehicle_id = trip_plan.vehicle_id

    def clean(self):
        super().clean()

        if not self.trip_assignment_id:
            return

        assignment = self.trip_assignment_id

        if assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise ValidationError("Cannot create a log for a cancelled trip.")

        if self.pk:
            previous = DailyTripLog.objects.filter(pk=self.pk).first()
            if previous and previous.log_status == self.LOG_STATUS_VERIFIED:
                raise ValidationError("Verified trip logs are read-only.")

        if self.collected_weight_kg is not None and self.collected_weight_kg <= 0:
            raise ValidationError("collected_weight_kg must be greater than 0.")

        if self.panchayat_id and self.ward_id:
            raise ValidationError(
                "Log cannot belong to both panchayat and ward."
            )
        if not self.panchayat_id and not self.ward_id:
            raise ValidationError(
                "Log must belong to either a panchayat or a ward."
            )

        # Capacity check
        trip_plan        = assignment.trip_plan_id
        vehicle_capacity = getattr(self.vehicle_id, "capacity",                None)
        plan_capacity    = getattr(trip_plan,        "max_vehicle_capacity_kg", None)
        capacity         = vehicle_capacity or plan_capacity

        if capacity and self.collected_weight_kg is not None:
            if Decimal(self.collected_weight_kg) > Decimal(capacity):
                raise ValidationError(
                    f"collected_weight_kg ({self.collected_weight_kg} kg) "
                    f"exceeds capacity ({capacity} kg)."
                )

    def save(self, *args, **kwargs):
        self.autofill_from_assignment()

        if not self.unique_id:
            self.unique_id = _generate_daily_trip_log_unique_id(
                self.company_id, self.project_id
            )

        self.full_clean()
        super().save(*args, **kwargs)

        # Mark assignment complete when submitted or verified
        if self.log_status in {self.LOG_STATUS_SUBMITTED, self.LOG_STATUS_VERIFIED}:
            assignment = self.trip_assignment_id
            if assignment.status != DailyTripAssignment.STATUS_COMPLETED:
                update_fields = ["status", "updated_at"]
                assignment.status = DailyTripAssignment.STATUS_COMPLETED
                if not assignment.actual_end_time:
                    assignment.actual_end_time = (
                        self.actual_end_time or timezone.localtime().time()
                    )
                    update_fields.append("actual_end_time")
                assignment.save(update_fields=update_fields)
python# ============================================================
# signals/daily_trip_assignment_signals.py
# ============================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.transport_masters.trip_plan_collection_point import TripPlanCollectionPoint


@receiver(post_save, sender=DailyTripAssignment)
def auto_populate_collection_points(sender, instance, created, **kwargs):
    """
    Fires after every DailyTripAssignment save.
    On creation: copies active TripPlanCollectionPoint rows into
    DailyTripCollectionPoint automatically, preserving sequence.
    Skips silently if stops already exist (safe for re-saves).
    """
    if not created:
        return

    if instance.trip_collection_points.filter(is_deleted=False).exists():
        return

    plan_cps = (
        TripPlanCollectionPoint.objects
        .filter(
            trip_plan_id=instance.trip_plan_id,
            is_active=True,
            is_deleted=False,
        )
        .select_related("collection_point_id", "bin_id")
        .order_by("sequence")
    )

    if not plan_cps.exists():
        return

    DailyTripCollectionPoint.objects.bulk_create([
        DailyTripCollectionPoint(
            trip_assignment_id=instance,
            collection_point_id=plan_cp.collection_point_id,
            bin_id=plan_cp.bin_id,
            sequence=plan_cp.sequence,
        )
        for plan_cp in plan_cps
    ])
python# ============================================================
# tasks/auto_create_daily_trips.py  (Celery beat — runs at midnight)
# ============================================================
from django.utils import timezone
from app.models.transport_masters.trip_plan import TripPlan
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment


def create_daily_trips_for_today():
    """
    For every ACTIVE + APPROVED TripPlan that has no
    DailyTripAssignment for today, create one.
    The post_save signal then auto-populates the stops.
    """
    today = timezone.localdate()

    active_plans = TripPlan.objects.filter(
        status=TripPlan.Status.ACTIVE,
        approval_status=TripPlan.ApprovalStatus.APPROVED,
        is_deleted=False,
    ).select_related(
        "staff_template_id",
        "vehicle_id",
        "company_id",
        "project_id",
        "panchayat_id",
        "ward_id",
        "waste_type_id",
    )

    for plan in active_plans:

        # Skip if already created for today
        if DailyTripAssignment.objects.filter(
            trip_plan_id=plan,
            trip_date=today,
            is_deleted=False,
        ).exists():
            continue

        # Resolve effective staff — use alt template if active today
        alt_template = (
            plan.staff_template_id.alternative_templates
            .filter(
                from_date__lte=today,
                to_date__gte=today,
                approval_status="APPROVED",
                is_deleted=False,
            )
            .first()
        )

        DailyTripAssignment.objects.create(
            company_id        = plan.company_id,
            project_id        = plan.project_id,
            trip_plan_id      = plan,
            staff_template_id = plan.staff_template_id,
            alt_staff_template_id = alt_template,
            panchayat_id      = plan.panchayat_id,
            ward_id           = plan.ward_id,
            waste_type_id     = plan.waste_type_id,
            vehicle_id        = plan.vehicle_id,
            trip_date         = today,
            scheduled_time    = plan.scheduled_time,
        )
        # post_save signal fires here →
        # DailyTripCollectionPoint rows auto-created from TripPlanCollectionPoint

Complete model summary
#ModelPurpose1StaffTemplatePermanent driver–operator team pairing2AlternativeStaffTemplateTemporary substitution for a date range3Collection_pointPhysical GPS location, panchayat or ward4TripPlanMaster route blueprint — WHO, WHERE, WHAT, WHEN5TripPlanCollectionPointMaster stop list per plan — copied into every daily trip6DailyTripAssignmentOne scheduled trip on one date7DailyTripCollectionPointIndividual stops for that day's trip — auto-populated from model 58BinCollectionEventImmutable scan audit record per bin9DailyTripLogEnd-of-trip summary, auto-created on last scan


i have all the files shattered. Your job is to club the new trip related files to a new master "schedule masters" folder -> like models, viewsets, serializers, seeder,  as mainscreen => 9 submodules
StaffTemplateapp.models.user_creations.staff_template2AlternativeStaffTemplateapp.models.user_creations.alternative_staff_template3Collection_pointapp.models.assets.collection_point4TripPlanapp.models.transport_masters.trip_plan5TripPlanCollectionPointapp.models.transport_masters.trip_plan_collection_point6DailyTripAssignmentapp.models.transport_masters.daily_trip_assignment7DailyTripCollectionPointapp.models.transport_masters.daily_trip_collection_point8BinCollectionEventapp.models.transport_masters.bin_collection_event9DailyTripLog



eg:-
router.register_group("schedule masters", "daily-trip-assigment", DailyTripAssignmentViewset)


