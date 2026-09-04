"""Complaint ticket transaction + audit tables.

Only `ComplaintRoutingRule` carries company/project here. Everything else in
this module hangs off a single `ComplaintTicket` by a CASCADE foreign key —
attachments, comments, the status/assignment/escalation/reopen histories,
feedback and notifications — so the ticket already answers "which tenant?".
Duplicating the pair onto each child row would add a column that can drift out
of sync with its parent for no gain: those tables are always reached through
their ticket, and the ticket queryset is already company-scoped by
`CompanyScopedViewSet`. Where a child list needs filtering directly (the
Feedback screen), it filters through the parent — see
`ComplaintFeedbackViewSet.get_queryset`.

Ported from the government backend. These are geo-agnostic, so they carry
over unchanged apart from import paths and the routing rule, whose optional
geo scope follows this project's Zone/Ward model (see `ticket.py`).
"""

from django.conf import settings
from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.customers.customercreation import CustomerCreation
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.complaint_management.masters import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintSlaRule,
    ComplaintStatus,
    ComplaintSubcategory,
    ComplaintTeam,
)
from app.models.complaint_management.ticket import ComplaintTicket


def generate_extra_detail_id():
    return f"CPTXTRA-{generate_unique_id()}"


def generate_attachment_id():
    return f"CPTATT-{generate_unique_id()}"


def generate_status_history_id():
    return f"CPTSH-{generate_unique_id()}"


def generate_assignment_history_id():
    return f"CPTAH-{generate_unique_id()}"


def generate_comment_id():
    return f"CPTCMT-{generate_unique_id()}"


def generate_routing_rule_id():
    return f"CPTRR-{generate_unique_id()}"


def generate_escalation_history_id():
    return f"CPTESC-{generate_unique_id()}"


def generate_feedback_id():
    return f"CPTFB-{generate_unique_id()}"


def generate_reopen_history_id():
    return f"CPTRO-{generate_unique_id()}"


def generate_notification_id():
    return f"CPTNTF-{generate_unique_id()}"


def complaint_attachment_upload_path(instance, filename):
    return f"uploads/complaint_ticket/{instance.ticket_id}_{filename}"


class ComplaintTicketExtraDetail(BaseMaster):
    """Category-specific dynamic key/value fields for a ticket."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_extra_detail_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="extra_details",
    )
    field_key = models.CharField(max_length=100)
    field_value = models.TextField(blank=True, null=True)
    field_type = models.CharField(max_length=50, default="text")
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Ticket Extra Detail"
        verbose_name_plural = "Complaint Ticket Extra Details"

    def __str__(self):
        return f"{self.field_key}={self.field_value}"


class ComplaintAttachment(BaseMaster):
    """File attachments for a complaint ticket."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_attachment_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_attachments",
    )
    uploaded_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_attachments",
    )

    file = models.FileField(upload_to=complaint_attachment_upload_path, null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_type = models.CharField(max_length=50, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Attachment"
        verbose_name_plural = "Complaint Attachments"

    def __str__(self):
        return self.file_name or self.unique_id


class ComplaintStatusHistory(BaseMaster):
    """Audit row written on every ticket status change."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_status_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="status_history_from",
    )
    to_status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        related_name="status_history_to",
    )
    changed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_status_changes",
    )
    changed_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_status_changes",
    )
    changed_by_system = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)
    visible_to_citizen = models.BooleanField(default=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Complaint Status History"
        verbose_name_plural = "Complaint Status History"

    def __str__(self):
        return f"{self.ticket_id}: {self.to_status_id}"


class ComplaintAssignmentHistory(BaseMaster):
    """Audit row written on every ticket (re)assignment."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_assignment_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="assignment_history",
    )
    from_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment_history_from",
    )
    to_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment_history_to",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_from",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_to",
    )
    from_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_from_staff",
    )
    to_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_to_staff",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_by",
    )
    assignment_reason = models.TextField(blank=True, null=True)

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Complaint Assignment History"
        verbose_name_plural = "Complaint Assignment History"

    def __str__(self):
        return f"{self.ticket_id} -> {self.to_team_id}"


class ComplaintComment(BaseMaster):
    """Comments / notes on a complaint ticket (internal or citizen-facing)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_comment_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    comment_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_comments",
    )
    comment_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_comments",
    )
    comment_text = models.TextField()
    is_internal = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Comment"
        verbose_name_plural = "Complaint Comments"

    def __str__(self):
        return f"{self.ticket_id} comment {self.unique_id}"


class ComplaintRoutingRule(BaseMaster):
    """Resolves a team/user/SLA for a ticket by category + geo + priority.

    Geo scope follows this project's model (state/district/panchayat/zone/
    ward) rather than government's local-body hierarchy. Empty fields mean
    "any".
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_routing_rule_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="complaint_routing_rules",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="complaint_routing_rules",
        db_column="project_id",
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="routing_rules",
    )
    subcategory = models.ForeignKey(
        ComplaintSubcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
        db_column="district_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
        db_column="panchayat_id",
    )
    zone = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
        db_column="zone_id",
    )
    ward = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
        db_column="ward_id",
    )
    priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.PROTECT,
        related_name="routing_rules",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
    )
    sla_rule = models.ForeignKey(
        ComplaintSlaRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_rules",
    )

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint Routing Rule"
        verbose_name_plural = "Complaint Routing Rules"

    def save(self, *args, **kwargs):
        # Tenancy follows the category, as with the SLA rule.
        if self.category_id:
            self.company_id_id = self.category.company_id_id
            self.project_id_id = self.category.project_id_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Route {self.category_id} -> {self.team_id}"


class ComplaintEscalationHistory(BaseMaster):
    """Audit row for each escalation (SLA breach or manual)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_escalation_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="escalation_history",
    )
    escalation_level = models.IntegerField(default=1)
    escalated_from_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_from",
    )
    escalated_to_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_to",
    )
    escalated_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_escalations",
    )
    escalated_to_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_escalations_staff",
    )
    reason = models.TextField(blank=True, null=True)
    escalated_by_system = models.BooleanField(default=False)

    escalated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-escalated_at"]
        verbose_name = "Complaint Escalation History"
        verbose_name_plural = "Complaint Escalation History"

    def __str__(self):
        return f"{self.ticket_id} esc L{self.escalation_level}"


class ComplaintFeedback(BaseMaster):
    """Citizen feedback captured after resolution (one per ticket)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_feedback_id,
        editable=False,
    )

    ticket = models.OneToOneField(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_feedback",
    )
    rating = models.IntegerField(null=True, blank=True)
    feedback_text = models.TextField(blank=True, null=True)
    is_issue_solved = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Complaint Feedback"
        verbose_name_plural = "Complaint Feedback"

    def __str__(self):
        return f"{self.ticket_id} feedback {self.rating}"


class ComplaintReopenHistory(BaseMaster):
    """Audit row written each time a ticket is reopened."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_reopen_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="reopen_history",
    )
    reopened_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_reopens",
    )
    reopened_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_reopens",
    )
    reopen_reason = models.TextField(blank=True, null=True)
    previous_status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reopen_history",
    )

    reopened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reopened_at"]
        verbose_name = "Complaint Reopen History"
        verbose_name_plural = "Complaint Reopen History"

    def __str__(self):
        return f"{self.ticket_id} reopened"


class ComplaintNotification(BaseMaster):
    """In-app notification for a grievance event (assign/escalate/resolve/reopen)."""

    EVENT_ASSIGNED = "ASSIGNED"
    EVENT_ESCALATED = "ESCALATED"
    EVENT_ESCALATED_TO = "ESCALATED_TO"
    EVENT_RESOLVED = "RESOLVED"
    EVENT_REOPENED = "REOPENED"

    EVENT_CHOICES = [
        (EVENT_ASSIGNED, "Assigned"),
        (EVENT_ESCALATED, "Escalated"),
        (EVENT_ESCALATED_TO, "Escalated To You"),
        (EVENT_RESOLVED, "Resolved"),
        (EVENT_REOPENED, "Reopened"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_notification_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    recipient_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="complaint_notifications",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="complaint_notifications",
    )

    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, null=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Complaint Notification"
        verbose_name_plural = "Complaint Notifications"
        indexes = [
            models.Index(fields=["recipient_staff", "is_read"]),
            models.Index(fields=["recipient_user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.ticket_id}"
