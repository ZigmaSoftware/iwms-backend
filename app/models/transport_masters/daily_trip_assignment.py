from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.trip_definition import TripDefinition
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.panchayat import Panchayat
from app.models.assets.collection_point import Collection_point
# from app.models.waste_types.subproperty import SubProperty
from app.models.user_creations.waste_collection_bluetooth import WasteType


def _generate_trip_assignment_unique_id(company_id, project_id):
    """
    Generates TRIP-YYYY-MM-NNN, where NNN is sequential per company+project+month.
    Inline import avoids circular-import at module load time.
    """
    today = timezone.localdate()
    prefix = f"TRIP-{today.year}-{today.month:02d}"
    count = DailyTripAssignment.objects.filter(
        company_id=company_id,
        project_id=project_id,
        unique_id__startswith=f"{prefix}-",
    ).count()
    return f"{prefix}-{count + 1:03d}"


class DailyTripAssignment(BaseMaster):

    STATUS_SCHEDULED = "Scheduled"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    APPROVAL_PENDING = "Pending"
    APPROVAL_APPROVED = "Approved"
    APPROVAL_REJECTED = "Rejected"

    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    # ------------------------------------------------------------------
    # IDENTIFIER
    # ------------------------------------------------------------------

    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    # ------------------------------------------------------------------
    # TENANCY
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # TRIP DEFINITION & STAFF
    # ------------------------------------------------------------------

    trip_definition_id = models.ForeignKey(
        TripDefinition,
        on_delete=models.PROTECT,
        db_column="trip_definition_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

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

    # ------------------------------------------------------------------
    # LOCATION
    # ------------------------------------------------------------------

    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    # ------------------------------------------------------------------
    # WASTE TYPE
    # ------------------------------------------------------------------

    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    # ------------------------------------------------------------------
    # SCHEDULING
    # ------------------------------------------------------------------

    trip_date = models.DateField()
    scheduled_time = models.TimeField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    # ------------------------------------------------------------------
    # STATUS & APPROVAL
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ------------------------------------------------------------------
    # META
    # ------------------------------------------------------------------

    class Meta:
        ordering = ["-trip_date", "-scheduled_time"]
        indexes = [
            models.Index(fields=["trip_date", "status"]),
            models.Index(fields=["trip_definition_id", "trip_date"]),
            models.Index(fields=["panchayat_id", "trip_date"]),
        ]

    # ------------------------------------------------------------------
    # UNIQUE_ID GENERATION
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.unique_id:
            self.unique_id = _generate_trip_assignment_unique_id(
                self.company_id, self.project_id
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id
