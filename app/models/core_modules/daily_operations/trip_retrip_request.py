"""Supervisor/admin request to close a trip that still has unfinished stops.

A driver who runs out of shift, fills the vehicle, or hits a blocked road can
neither finish the remaining stops nor legitimately end the trip — before
this, the assignment simply sat `In Progress` forever, because nothing
auto-closes a trip and a `Skipped` stop permanently blocks
`mark_completed_if_all_cps_collected`.

The Re-Trip flow gives that state an exit:

    N stops left
      -> TripRetripRequest(Pending) + mandatory reason; trip STAYS In Progress
      -> supervisor/admin reviews, picks what carries over, approves
      -> old assignment ends, a NEW assignment on the same trip plan is
         created carrying only the selected stops

The trip deliberately keeps its `In Progress` status while a request is
pending so `DailyTripAssignment.STATUS_CHOICES` stays untouched — the app
learns about the pending request from this model instead of a new status
value. Ported from the government app's identically-named model, adapted for
private's company/project scoping (see `app/services/retrip_service.py`).
"""

from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_retrip_request_id():
    return f"RETRIP-{generate_unique_id()}"


class TripRetripRequest(BaseMaster):
    STATUS_PENDING = "Pending"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_retrip_request_id,
        editable=False,
    )

    # ── Tenancy (mirrors VehicleBreakdown) ────────────────────────────
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    assignment_id = models.CharField(max_length=30)
    requested_by_id = models.CharField(max_length=30, null=True, blank=True)

    # Mandatory — the whole point of the gate is that the requester has to
    # say why the trip is being cut short.
    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    # Snapshot taken when the request is raised. Stops can change between
    # request and approval, so the supervisor's screen shows live counts —
    # these are the audit record of what was actually outstanding then.
    pending_bin_count = models.IntegerField(default=0)
    pending_household_count = models.IntegerField(default=0)
    pending_snapshot = models.JSONField(default=dict, blank=True)

    reviewed_by_id = models.CharField(max_length=30, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remarks = models.TextField(null=True, blank=True)

    # The continuation trip created on approval.
    new_assignment_id = models.CharField(max_length=30, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Re-Trip Request"
        verbose_name_plural = "Re-Trip Requests"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.unique_id} ({self.assignment_id} · {self.status})"

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    def mark_reviewed(self, *, status, by=None, remarks=None, new_assignment=None):
        self.status = status
        self.reviewed_by_id = by.staff_unique_id if by else None
        self.reviewed_at = timezone.now()
        self.review_remarks = remarks
        if new_assignment is not None:
            self.new_assignment_id = new_assignment.unique_id
        self.save(update_fields=[
            "status", "reviewed_by_id", "reviewed_at", "review_remarks",
            "new_assignment_id", "updated_at",
        ])

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
    def assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        if self.assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.assignment_id).first()
        return None

    @property
    def requested_by(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        if self.requested_by_id:
            return Staffcreation.objects.filter(staff_unique_id=self.requested_by_id).first()
        return None

    @property
    def reviewed_by(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        if self.reviewed_by_id:
            return Staffcreation.objects.filter(staff_unique_id=self.reviewed_by_id).first()
        return None

    @property
    def new_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        if self.new_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.new_assignment_id).first()
        return None
