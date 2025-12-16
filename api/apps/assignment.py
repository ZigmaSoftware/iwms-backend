from django.db import models
from django.db.models import Q

from .utils.comfun import generate_unique_id
from .ward import Ward
from .customercreation import CustomerCreation
from .userCreation import User


def generate_assignment_id():
    return f"ASSIGN{generate_unique_id()}"


class DailyAssignment(models.Model):

    ASSIGNMENT_TYPE_CHOICES = [
        ("primary", "Primary"),
        ("temporary", "Temporary"),
        ("emergency", "Emergency"),
    ]

    SHIFT_CHOICES = [
        ("morning", "Morning"),
        ("afternoon", "Afternoon"),
        ("full_day", "Full Day"),
    ]

    unique_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_assignment_id,
        editable=False,
    )

    # IMPORTANT: admin-controlled, not auto
    date = models.DateField()

    ward = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="assignments",
    )

    # Exception-level override only
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )

    driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="assignments_as_driver",
    )

    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="assignments_as_operator",
    )

    assignment_type = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_TYPE_CHOICES,
        default="primary",
    )

    shift = models.CharField(
        max_length=20,
        choices=SHIFT_CHOICES,
        default="full_day",
    )

    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    cancelled_reason = models.CharField(
        max_length=255, null=True, blank=True
    )
    cancelled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_assignments",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_daily_assignments"
        ordering = ["-date", "-created_at"]

        # 🔒 HARD BUSINESS RULE
        constraints = [
            models.UniqueConstraint(
                fields=["date", "ward", "shift"],
                condition=Q(is_active=True),
                name="uniq_active_ward_per_shift_per_day",
            )
        ]

    def __str__(self):
        return f"{self.date} | {self.ward} | {self.shift}"
