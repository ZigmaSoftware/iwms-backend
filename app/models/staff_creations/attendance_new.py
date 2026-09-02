"""New face-recognition attendance punch log.

Sits alongside `app.models.staff_creations.attendance.Recognized` (the older,
simpler punch table `AttendanceListViewSet` already reads). This one mirrors
a colleague's separate reference implementation (a standalone Django project
using InsightFace + liveness detection) — same field shape, adapted onto
`Staffcreation` instead of their own `Employee` model, and onto this
project's `BaseMaster` conventions (is_active/is_deleted, tenancy).

Not wired to any viewset/serializer yet — this is the model + migration only.
"""

from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_attendance_new_unique_id():
    return f"ATTN-{generate_unique_id()}"


class AttendanceNew(BaseMaster):
    LOG_TYPE_IN = "IN"
    LOG_TYPE_OUT = "OUT"
    LOG_TYPE_CHOICES = [
        (LOG_TYPE_IN, "In"),
        (LOG_TYPE_OUT, "Out"),
    ]

    CAPTURE_METHOD_FACE = "face"
    CAPTURE_METHOD_MANUAL = "manual"
    CAPTURE_METHOD_OFFLINE = "offline"
    CAPTURE_METHOD_CHOICES = [
        (CAPTURE_METHOD_FACE, "Face"),
        (CAPTURE_METHOD_MANUAL, "Manual"),
        (CAPTURE_METHOD_OFFLINE, "Offline"),
    ]

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_attendance_new_unique_id,
        editable=False,
    )

    staff = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        db_column="staff_id",
        related_name="attendance_new_records",
    )

    log_type = models.CharField(max_length=3, choices=LOG_TYPE_CHOICES, default=LOG_TYPE_IN)
    capture_method = models.CharField(
        max_length=10, choices=CAPTURE_METHOD_CHOICES, default=CAPTURE_METHOD_FACE
    )

    # The actual punch instant (device time for offline syncs, server time
    # otherwise) — mirrors the colleague's `records` field.
    punch_at = models.DateTimeField()
    punch_date = models.DateField()
    punch_time = models.TimeField()

    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    captured_image_path = models.CharField(max_length=255, null=True, blank=True)
    similarity_score = models.FloatField(null=True, blank=True)
    bio_metric_id = models.CharField(max_length=100, null=True, blank=True)

    # True for punches captured offline on the device and synced later, so
    # `punch_at` reflects the real capture time rather than the sync time.
    is_offline = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendancenew"
        ordering = ["-punch_at"]
        verbose_name = "Attendance (New)"
        verbose_name_plural = "Attendance (New)"
        indexes = [
            models.Index(fields=["staff", "punch_date"]),
            models.Index(fields=["punch_date"]),
        ]

    def __str__(self):
        return f"{self.staff_id} {self.log_type} {self.punch_at}"

    def save(self, *args, **kwargs):
        if self.punch_at:
            self.punch_date = self.punch_date or self.punch_at.date()
            self.punch_time = self.punch_time or self.punch_at.time()
        super().save(*args, **kwargs)
