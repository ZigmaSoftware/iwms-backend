from django.db import models, transaction
from django.utils import timezone

from app.utils.base_models import BaseMaster


def _generate_vehicle_breakdown_id():
    today = timezone.localdate()
    prefix = f"VBD-{today.year}-{today.month:02d}"
    with transaction.atomic():
        existing = (
            VehicleBreakdown.objects.select_for_update()
            .filter(unique_id__startswith=f"{prefix}-")
            .values_list("unique_id", flat=True)
        )
        max_seq = 0
        for uid in existing:
            try:
                seq = int(uid.rsplit("-", 1)[-1])
                if seq > max_seq:
                    max_seq = seq
            except (ValueError, IndexError):
                pass
        return f"{prefix}-{max_seq + 1:03d}"


class VehicleBreakdown(BaseMaster):

    STATUS_REPORTED = "REPORTED"
    STATUS_REPLACEMENT_ARRANGED = "REPLACEMENT_ARRANGED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (STATUS_REPORTED, "Reported"),
        (STATUS_REPLACEMENT_ARRANGED, "Replacement Arranged"),
        (STATUS_REJECTED, "Rejected"),
    ]

    APPROVAL_PENDING = "PENDING"
    APPROVAL_APPROVED = "APPROVED"
    APPROVAL_REJECTED = "REJECTED"

    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    BREAKDOWN_REASON_CHOICES = [
        ("FLAT_TYRE", "Flat Tyre"),
        ("ENGINE_FAILURE", "Engine Failure"),
        ("ACCIDENT", "Accident"),
        ("ELECTRICAL", "Electrical Fault"),
        ("OVERHEATING", "Overheating"),
        ("OTHER", "Other"),
    ]

    # ── Identifier ──────────────────────────────────────────────────
    unique_id = models.CharField(
        max_length=50,
        primary_key=True,
        editable=False,
        db_index=True,
    )

    # ── Tenancy ─────────────────────────────────────────────────────
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    # ── Trip Reference ───────────────────────────────────────────────
    trip_assignment_id = models.CharField(max_length=50, null=True, blank=True)

    # ── Vehicles ─────────────────────────────────────────────────────
    breakdown_vehicle_id = models.CharField(max_length=30, null=True, blank=True)
    # Null until the supervisor arranges a replacement at /verify/ — the
    # driver reporting a breakdown usually doesn't know it yet.
    replacement_vehicle_id = models.CharField(max_length=30, null=True, blank=True)

    # ── Replacement Staff (assigned later by the supervisor) ──────────
    replacement_driver_id = models.CharField(max_length=30, null=True, blank=True)
    replacement_operator_id = models.CharField(max_length=30, null=True, blank=True)

    # ── Created AlternativeStaffTemplate (set during approval) ───────
    alt_staff_template_id = models.CharField(max_length=50, null=True, blank=True)

    # ── Continuation trip created on verify (mirrors TripRetripRequest.new_assignment) ──
    new_assignment = models.CharField(max_length=50, null=True, blank=True)

    # ── Breakdown Details ─────────────────────────────────────────────
    breakdown_time = models.TimeField(null=True, blank=True)
    breakdown_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    breakdown_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    breakdown_location = models.CharField(max_length=255, null=True, blank=True)
    collected_weight_before_breakdown_kg = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Weight already collected by the broken vehicle before the breakdown occurred."
    )
    breakdown_reason = models.CharField(
        max_length=20,
        choices=BREAKDOWN_REASON_CHOICES,
        default="OTHER",
    )
    breakdown_remarks = models.TextField(null=True, blank=True)

    # ── Status & Approval ─────────────────────────────────────────────
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_REPORTED,
        db_index=True,
    )
    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_PENDING,
        db_index=True,
    )
    approved_by = models.CharField(max_length=30, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("vehicle_breakdown_list", "vehicle_breakdown_detail")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "approval_status"]),
            models.Index(fields=["company_id", "project_id"]),
        ]

    def save(self, *args, **kwargs):
        if not self.unique_id:
            self.unique_id = _generate_vehicle_breakdown_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id

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
    def trip_assignment(self):
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        if self.trip_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        return None

    @property
    def breakdown_vehicle(self):
        from app.models.transport_masters.vehicleCreation import VehicleCreation
        if self.breakdown_vehicle_id:
            return VehicleCreation.objects.filter(unique_id=self.breakdown_vehicle_id).first()
        return None

    @property
    def replacement_vehicle(self):
        from app.models.transport_masters.vehicleCreation import VehicleCreation
        if self.replacement_vehicle_id:
            return VehicleCreation.objects.filter(unique_id=self.replacement_vehicle_id).first()
        return None

    @property
    def replacement_driver(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.replacement_driver_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.replacement_driver_id).first()
        return None

    @property
    def replacement_operator(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.replacement_operator_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.replacement_operator_id).first()
        return None

    @property
    def alt_staff_template(self):
        from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
        if self.alt_staff_template_id:
            return AlternativeStaffTemplate.objects.filter(unique_id=self.alt_staff_template_id).first()
        return None

    @property
    def new_assignment_obj(self):
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        if self.new_assignment:
            return DailyTripAssignment.objects.filter(unique_id=self.new_assignment).first()
        return None

    @property
    def approved_by_user(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.approved_by:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.approved_by).first()
        return None


def vehicle_breakdown_photo_upload_path(instance, filename):
    return f"uploads/vehicle_breakdown/{instance.breakdown_id}/{filename}"


class VehicleBreakdownPhoto(models.Model):
    """Photo evidence attached when a breakdown is reported (e.g. the flat
    tyre, the accident scene). Optional — a breakdown can have zero, one, or
    several."""

    breakdown_id = models.CharField(max_length=50, null=True, blank=True)
    photo = models.ImageField(upload_to=vehicle_breakdown_photo_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("vehicle_breakdown_photo_list", "vehicle_breakdown_photo_detail")

    def __str__(self):
        return f"{self.breakdown_id} photo #{self.pk}"

    @property
    def breakdown(self):
        if self.breakdown_id:
            return VehicleBreakdown.objects.filter(unique_id=self.breakdown_id).first()
        return None