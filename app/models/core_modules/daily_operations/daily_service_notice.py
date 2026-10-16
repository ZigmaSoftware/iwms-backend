from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_daily_service_notice_id():
    return f"DSN-{generate_unique_id()}"


class DailyServiceNotice(BaseMaster):
    """An audited plan-level decision that collection will not run on a date."""

    STATUS_ACTIVE = "ACTIVE"
    STATUS_REVOKED = "REVOKED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_REVOKED, "Revoked"),
    ]

    REASON_WEATHER = "WEATHER"
    REASON_FLOOD = "FLOOD"
    REASON_HOLIDAY = "HOLIDAY"
    REASON_STAFF_UNAVAILABLE = "STAFF_UNAVAILABLE"
    REASON_VEHICLE_TECHNICAL = "VEHICLE_TECHNICAL"
    REASON_SAFETY = "SAFETY"
    REASON_OTHER = "OTHER"
    REASON_CHOICES = [
        (REASON_WEATHER, "Severe weather"),
        (REASON_FLOOD, "Flooding"),
        (REASON_HOLIDAY, "Public holiday"),
        (REASON_STAFF_UNAVAILABLE, "Staff unavailable"),
        (REASON_VEHICLE_TECHNICAL, "Vehicle or technical issue"),
        (REASON_SAFETY, "Safety issue"),
        (REASON_OTHER, "Other"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_daily_service_notice_id,
        editable=False,
    )
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    trip_plan_id = models.CharField(max_length=30, db_index=True)
    supervisor_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    service_date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    reason_code = models.CharField(max_length=30, choices=REASON_CHOICES)
    reason_text = models.CharField(max_length=500, blank=True, default="")
    recipient_staff_ids = models.JSONField(default=list, blank=True)
    recipient_customer_ids = models.JSONField(default=list, blank=True)
    staff_notified_count = models.PositiveIntegerField(default=0)
    customer_notified_count = models.PositiveIntegerField(default=0)
    notification_failed_count = models.PositiveIntegerField(default=0)
    notified_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by_id = models.CharField(max_length=50, null=True, blank=True)
    revoked_reason = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_plan_id", "service_date"],
                name="uniq_daily_service_notice_plan_date",
            ),
        ]
        indexes = [
            models.Index(fields=["supervisor_id", "service_date", "status"]),
        ]

    def __str__(self):
        return f"{self.trip_plan_id} - {self.service_date} - {self.status}"
