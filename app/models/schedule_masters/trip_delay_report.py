"""Driver-reported delays that are NOT a breakdown.

A puncture, a minor repair, a blocked road, a queue at the plant: the vehicle
is still serviceable and the trip carries on, so none of the breakdown
machinery applies — no replacement vehicle, no alternative crew, no
continuation assignment. What the supervisor needs is simply to know the trip
is running late and why.

That is the whole design: this is an append-only log with an acknowledgement
workflow, deliberately kept out of `VehicleBreakdown` (whose OneToOne to the
assignment, replacement-vehicle FKs and approval flow all exist to swap a dead
vehicle out mid-trip, and none of which a puncture needs).

Unlike a breakdown this is a plain ForeignKey to the assignment: one trip can
legitimately be delayed several times in a day.
"""

from django.db import models, transaction
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.staff_creations.staffcreation import Staffcreation


def _generate_trip_delay_id():
    """`DLY-YYYY-MM-NNN`, sequential within the month.

    Mirrors `_generate_vehicle_breakdown_id` — same select_for_update pattern
    so two drivers reporting at once cannot mint the same id.
    """
    today = timezone.localdate()
    prefix = f"DLY-{today.year}-{today.month:02d}"
    with transaction.atomic():
        existing = (
            TripDelayReport.objects.select_for_update()
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


class TripDelayReport(BaseMaster):

    STATUS_REPORTED = "REPORTED"
    STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
    STATUS_RESOLVED = "RESOLVED"

    STATUS_CHOICES = [
        (STATUS_REPORTED, "Reported"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    DELAY_REASON_CHOICES = [
        ("PUNCTURE", "Puncture / Tyre"),
        ("MINOR_REPAIR", "Minor Repair"),
        ("TRAFFIC", "Traffic"),
        ("ROAD_BLOCKED", "Road Blocked"),
        ("FUEL", "Refuelling"),
        ("WEATHER", "Weather"),
        ("PUBLIC_OBSTRUCTION", "Public Obstruction"),
        ("WAITING_AT_PLANT", "Waiting at Plant"),
        ("OTHER", "Other"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=_generate_trip_delay_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="trip_delay_reports",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="trip_delay_reports",
        db_column="project_id",
    )

    # ForeignKey, NOT OneToOne: a trip can be delayed more than once.
    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.CASCADE,
        related_name="delay_reports",
        db_column="trip_assignment_id",
    )

    reported_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_trip_delays",
        db_column="reported_by",
    )

    delay_reason = models.CharField(
        max_length=30,
        choices=DELAY_REASON_CHOICES,
    )
    # The point of the whole feature — enforced non-blank at the serializer,
    # where a friendly message can be returned.
    delay_remarks = models.TextField()

    # Optional, but what lets a supervisor tell "10 minutes" from "two hours"
    # without reading every remark.
    estimated_delay_minutes = models.PositiveIntegerField(null=True, blank=True)

    delay_time = models.TimeField(null=True, blank=True)
    delay_lat = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    delay_lng = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    delay_location = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_REPORTED,
    )

    acknowledged_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_trip_delays",
        db_column="acknowledged_by",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    supervisor_remarks = models.TextField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_tripdelayreport"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company_id", "project_id", "status"]),
            models.Index(fields=["trip_assignment_id"]),
        ]

    def __str__(self):
        return f"{self.unique_id} ({self.get_delay_reason_display()})"

    def save(self, *args, **kwargs):
        # Stamp the wall-clock time of the delay on first write so the
        # supervisor list can show "reported at 09:41" without deriving it from
        # created_at in every serializer.
        if not self.delay_time:
            self.delay_time = timezone.localtime().time()
        # Inherit tenant scope from the trip — a delay is never in a different
        # company/project than the assignment it belongs to, and a null here
        # would hide the row from every company-scoped list.
        if self.trip_assignment_id_id:
            if not self.company_id_id:
                self.company_id_id = self.trip_assignment_id.company_id_id
            if not self.project_id_id:
                self.project_id_id = self.trip_assignment_id.project_id_id
        super().save(*args, **kwargs)

    def mark_acknowledged(self, *, by=None, remarks=None):
        """Supervisor has seen it. Idempotent."""
        if self.status != self.STATUS_REPORTED:
            return False
        self.status = self.STATUS_ACKNOWLEDGED
        self.acknowledged_by = by
        self.acknowledged_at = timezone.now()
        if remarks:
            self.supervisor_remarks = remarks
        self.save(update_fields=[
            "status", "acknowledged_by", "acknowledged_at",
            "supervisor_remarks", "updated_at",
        ])
        return True

    def mark_resolved(self, *, remarks=None):
        """Back on route. Idempotent."""
        if self.status == self.STATUS_RESOLVED:
            return False
        self.status = self.STATUS_RESOLVED
        self.resolved_at = timezone.now()
        if remarks:
            self.supervisor_remarks = remarks
        self.save(update_fields=[
            "status", "resolved_at", "supervisor_remarks", "updated_at",
        ])
        return True
