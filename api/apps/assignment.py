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

    # Current status tracking
    current_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("skipped", "Skipped"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )

    # Driver/operator completion tracking
    driver_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("completed", "Completed"),
        ],
        default="pending",
    )
    operator_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("completed", "Completed"),
        ],
        default="pending",
    )
    driver_completed_at = models.DateTimeField(null=True, blank=True)
    operator_completed_at = models.DateTimeField(null=True, blank=True)

    # Completion tracking
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_assignments",
    )

    # Skip tracking
    skipped_at = models.DateTimeField(null=True, blank=True)
    skipped_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="skipped_assignments",
    )
    skip_reason = models.CharField(max_length=255, null=True, blank=True)

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


class AssignmentStatusHistory(models.Model):
    """
    Tracks every status change of an assignment.
    """

    STATUS_CHOICES = [
        ("created", "Created"),
        ("in_progress", "In Progress"),
        ("driver_completed", "Driver Completed"),
        ("operator_completed", "Operator Completed"),
        ("completed", "Completed"),
        ("skipped", "Skipped by Driver"),
        ("cancelled", "Cancelled by Admin"),
    ]

    assignment = models.ForeignKey(
        DailyAssignment,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment_status_changes",
    )
    reason = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    class Meta:
        db_table = "api_assignment_status_history"
        ordering = ["-timestamp"]
        verbose_name = "Assignment Status History"
        verbose_name_plural = "Assignment Status Histories"
        indexes = [
            models.Index(fields=["assignment", "-timestamp"]),
            models.Index(fields=["status", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.assignment.ward} - {self.status} at {self.timestamp}"


class DriverCollectionLog(models.Model):
    """
    Detailed log of driver's collection activities.
    """

    ACTION_CHOICES = [
        ("started_navigation", "Started Navigation"),
        ("arrived", "Arrived at Location"),
        ("collection_started", "Collection Started"),
        ("collection_completed", "Collection Completed"),
        ("skipped", "Skipped"),
    ]

    assignment = models.ForeignKey(
        DailyAssignment,
        on_delete=models.CASCADE,
        related_name="collection_logs",
    )

    driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="collection_logs",
    )

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    skip_reason = models.CharField(max_length=255, null=True, blank=True)
    waste_weight = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    photo_url = models.CharField(max_length=500, null=True, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "api_driver_collection_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["assignment", "-timestamp"]),
            models.Index(fields=["driver", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.driver} - {self.action} at {self.timestamp}"


class AssignmentCustomerStatus(models.Model):
    """
    Per-customer assignment status tracked by operators.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("collected", "Collected"),
        ("skipped", "Skipped"),
        ("later", "Later"),
    ]

    assignment = models.ForeignKey(
        DailyAssignment,
        on_delete=models.CASCADE,
        related_name="customer_statuses",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.CASCADE,
        related_name="assignment_statuses",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    skip_reason = models.CharField(max_length=255, null=True, blank=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment_customer_statuses",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    class Meta:
        db_table = "api_assignment_customer_status"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "customer"],
                name="uniq_assignment_customer_status",
            )
        ]
        indexes = [
            models.Index(fields=["assignment", "-updated_at"]),
            models.Index(fields=["customer", "-updated_at"]),
            models.Index(fields=["status", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.assignment} - {self.customer} ({self.status})"
