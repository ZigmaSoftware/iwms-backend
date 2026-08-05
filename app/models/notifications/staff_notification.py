from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.user_creations.staffcreation import Staffcreation


def generate_staff_notification_id():
    return f"STFNTF-{generate_unique_id()}"


class StaffNotification(BaseMaster):
    """General-purpose in-app notification for a staff login (driver/operator/
    supervisor). Always created via `app.services.staff_notification_service.
    notify_staff` — that is the single place new notification types get added.

    No push-notification delivery yet (private has no FCM/push integration),
    so this is in-app only: a row here plus whatever list/badge UI reads it.
    """

    TYPE_VEHICLE_BREAKDOWN_REPORTED = "VEHICLE_BREAKDOWN_REPORTED"
    TYPE_VEHICLE_REPLACEMENT_APPROVED = "VEHICLE_REPLACEMENT_APPROVED"
    TYPE_VEHICLE_REPLACEMENT_REJECTED = "VEHICLE_REPLACEMENT_REJECTED"
    TYPE_RETRIP_REQUESTED = "RETRIP_REQUESTED"
    TYPE_RETRIP_APPROVED = "RETRIP_APPROVED"
    TYPE_RETRIP_REJECTED = "RETRIP_REJECTED"

    TYPE_CHOICES = [
        (TYPE_VEHICLE_BREAKDOWN_REPORTED, "Vehicle Breakdown Reported"),
        (TYPE_VEHICLE_REPLACEMENT_APPROVED, "Vehicle Replacement Approved"),
        (TYPE_VEHICLE_REPLACEMENT_REJECTED, "Vehicle Replacement Rejected"),
        (TYPE_RETRIP_REQUESTED, "Re-Trip Requested"),
        (TYPE_RETRIP_APPROVED, "Re-Trip Approved"),
        (TYPE_RETRIP_REJECTED, "Re-Trip Rejected"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_staff_notification_id,
        editable=False,
    )

    recipient_staff = models.ForeignKey(
        Staffcreation,
        on_delete=models.CASCADE,
        related_name="app_notifications",
        to_field="staff_unique_id",
        db_column="recipient_staff_id",
    )

    notification_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, null=True)
    data = models.JSONField(default=dict, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Staff Notification"
        verbose_name_plural = "Staff Notifications"
        indexes = [
            models.Index(fields=["recipient_staff", "is_read"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.recipient_staff_id}"
