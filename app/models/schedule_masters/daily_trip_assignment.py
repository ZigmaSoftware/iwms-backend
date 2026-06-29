from django.db import connection, models, transaction
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.user_creations.waste_collection_bluetooth import WasteType


def _generate_trip_assignment_unique_id(company_id, project_id):
    """
    Generates TRIP-YYYY-MM-NNN with a globally unique sequence for the month.
    The unique_id column has no per-company constraint, so the NNN counter must
    be global (not scoped per company+project) to avoid cross-tenant collisions.
    Uses select_for_update() to serialize concurrent inserts.
    """
    today = timezone.localdate()
    prefix = f"TRIP-{today.year}-{today.month:02d}"
    from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint

    with transaction.atomic():
        assignment_ids = (
            DailyTripAssignment.objects.select_for_update()
            .filter(unique_id__startswith=f"{prefix}-")
            .values_list("unique_id", flat=True)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT DISTINCT trip_assignment_id
                FROM {DailyTripCollectionPoint._meta.db_table}
                WHERE trip_assignment_id LIKE %s
                """,
                [f"{prefix}-%"],
            )
            collection_point_assignment_ids = [row[0] for row in cursor.fetchall()]
        max_seq = 0
        for uid in set(assignment_ids).union(collection_point_assignment_ids):
            try:
                seq = int(uid.rsplit("-", 1)[-1])
                if seq > max_seq:
                    max_seq = seq
            except (ValueError, IndexError):
                pass
        return f"{prefix}-{max_seq + 1:03d}"


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
    # TRIP PLAN & STAFF
    # ------------------------------------------------------------------

    trip_plan_id = models.ForeignKey(
        TripPlan,
        on_delete=models.PROTECT,
        db_column="trip_plan_id",
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
        null=True,
        blank=True,
    )

    wards = models.ManyToManyField(
        Ward,
        related_name="daily_trip_assignments_m2m",
        blank=True,
    )

    # ------------------------------------------------------------------
    # WASTE TYPE
    # ------------------------------------------------------------------

    waste_type_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of waste type unique_ids assigned to this daily trip plan.",
    )

    # Multiple waste types for household collection stops on this trip
    household_waste_type_ids = models.ManyToManyField(
        WasteType,
        related_name="household_trip_assignments",
        blank=True,
    )

    # ------------------------------------------------------------------
    # VEHICLE (explicit for operator-mobile flow)
    # ------------------------------------------------------------------

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
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
            models.Index(fields=["trip_plan_id", "trip_date"]),
            models.Index(fields=["panchayat_id", "trip_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_plan_id", "trip_date"],
                name="uniq_daily_trip_plan_per_date",
            ),
        ]

    # ------------------------------------------------------------------
    # UNIQUE_ID GENERATION
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        if self.trip_plan_id:
            self.staff_template_id = self.staff_template_id or self.trip_plan_id.staff_template_id
            self.vehicle_id = self.vehicle_id or self.trip_plan_id.vehicle_id
            self.panchayat_id = self.panchayat_id or self.trip_plan_id.panchayat_id
            self.scheduled_time = self.scheduled_time or self.trip_plan_id.scheduled_time
            self.waste_type_ids = self.waste_type_ids or self.trip_plan_id.waste_type_ids
        if not self.unique_id:
            with transaction.atomic():
                self.unique_id = _generate_trip_assignment_unique_id(
                    self.company_id, self.project_id
                )
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id

    @property
    def primary_waste_type(self):
        if not self.waste_type_ids:
            return None
        return WasteType.objects.filter(
            unique_id=self.waste_type_ids[0],
            is_deleted=False,
        ).first()

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
