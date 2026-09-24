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

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    field_key = models.CharField(max_length=100)
    field_value = models.TextField(blank=True, null=True)
    field_type = models.CharField(max_length=50, default="text")
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_ticket_extra_detail_list", "complaint_ticket_extra_detail_detail")

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Ticket Extra Detail"
        verbose_name_plural = "Complaint Ticket Extra Details"

    def __str__(self):
        return f"{self.field_key}={self.field_value}"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None


class ComplaintAttachment(BaseMaster):
    """File attachments for a complaint ticket."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_attachment_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    uploaded_by_customer_id = models.CharField(max_length=30, null=True, blank=True)
    uploaded_by_user_id = models.CharField(max_length=30, null=True, blank=True)

    file = models.FileField(upload_to=complaint_attachment_upload_path, null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_type = models.CharField(max_length=50, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_attachment_list", "complaint_attachment_detail")

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Attachment"
        verbose_name_plural = "Complaint Attachments"

    def __str__(self):
        return self.file_name or self.unique_id

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def uploaded_by_customer(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        if self.uploaded_by_customer_id:
            return CustomerCreation.objects.filter(unique_id=self.uploaded_by_customer_id).first()
        return None

    @property
    def uploaded_by_user(self):
        from django.conf import settings
        if self.uploaded_by_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.uploaded_by_user_id).first()
        return None


class ComplaintStatusHistory(BaseMaster):
    """Audit row written on every ticket status change."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_status_history_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    from_status_id = models.CharField(max_length=30, null=True, blank=True)
    to_status_id = models.CharField(max_length=30, null=True, blank=True)
    changed_by_user_id = models.CharField(max_length=30, null=True, blank=True)
    changed_by_customer_id = models.CharField(max_length=30, null=True, blank=True)
    changed_by_system = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)
    visible_to_citizen = models.BooleanField(default=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_status_history_list", "complaint_status_history_detail")

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Complaint Status History"
        verbose_name_plural = "Complaint Status History"

    def __str__(self):
        return f"{self.ticket_id}: {self.to_status_id}"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def from_status(self):
        from app.models.core_modules.complaint_management.masters import ComplaintStatus
        if self.from_status_id:
            return ComplaintStatus.objects.filter(unique_id=self.from_status_id).first()
        return None

    @property
    def to_status(self):
        from app.models.core_modules.complaint_management.masters import ComplaintStatus
        if self.to_status_id:
            return ComplaintStatus.objects.filter(unique_id=self.to_status_id).first()
        return None

    @property
    def changed_by_user(self):
        from django.conf import settings
        if self.changed_by_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.changed_by_user_id).first()
        return None

    @property
    def changed_by_customer(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        if self.changed_by_customer_id:
            return CustomerCreation.objects.filter(unique_id=self.changed_by_customer_id).first()
        return None


class ComplaintAssignmentHistory(BaseMaster):
    """Audit row written on every ticket (re)assignment."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_assignment_history_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    from_user_id = models.CharField(max_length=30, null=True, blank=True)
    to_user_id = models.CharField(max_length=30, null=True, blank=True)
    from_staff_id = models.CharField(max_length=30, null=True, blank=True)
    to_staff_id = models.CharField(max_length=30, null=True, blank=True)
    assigned_by_id = models.CharField(max_length=30, null=True, blank=True)
    assignment_reason = models.TextField(blank=True, null=True)

    assigned_at = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_assignment_history_list", "complaint_assignment_history_detail")

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Complaint Assignment History"
        verbose_name_plural = "Complaint Assignment History"

    def __str__(self):
        return f"{self.ticket_id} -> {self.to_staff_id}"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def from_user(self):
        from django.conf import settings
        if self.from_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.from_user_id).first()
        return None

    @property
    def to_user(self):
        from django.conf import settings
        if self.to_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.to_user_id).first()
        return None

    @property
    def from_staff(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        if self.from_staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.from_staff_id).first()
        return None

    @property
    def to_staff(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        if self.to_staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.to_staff_id).first()
        return None

    @property
    def assigned_by(self):
        from django.conf import settings
        if self.assigned_by_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.assigned_by_id).first()
        return None


class ComplaintComment(BaseMaster):
    """Comments / notes on a complaint ticket (internal or citizen-facing)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_comment_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    comment_by_user_id = models.CharField(max_length=30, null=True, blank=True)
    comment_by_customer_id = models.CharField(max_length=30, null=True, blank=True)
    comment_text = models.TextField()
    is_internal = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_comment_list", "complaint_comment_detail")

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Comment"
        verbose_name_plural = "Complaint Comments"

    def __str__(self):
        return f"{self.ticket_id} comment {self.unique_id}"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def comment_by_user(self):
        from django.conf import settings
        if self.comment_by_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.comment_by_user_id).first()
        return None

    @property
    def comment_by_customer(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        if self.comment_by_customer_id:
            return CustomerCreation.objects.filter(unique_id=self.comment_by_customer_id).first()
        return None


class ComplaintRoutingRule(BaseMaster):
    """Resolves a department/user/SLA for a ticket by category + geo + priority.

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

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    category_id = models.CharField(max_length=30, null=True, blank=True)
    subcategory_id = models.CharField(max_length=30, null=True, blank=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)
    priority_id = models.CharField(max_length=30, null=True, blank=True)
    user_id = models.CharField(max_length=30, null=True, blank=True)
    sla_rule_id = models.CharField(max_length=30, null=True, blank=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_routing_rule_list", "complaint_routing_rule_detail")

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint Routing Rule"
        verbose_name_plural = "Complaint Routing Rules"

    def save(self, *args, **kwargs):
        # Tenancy follows the category, as with the SLA rule.
        if self.category_id:
            from app.models.core_modules.complaint_management.masters import ComplaintCategory
            cat = ComplaintCategory.objects.filter(unique_id=self.category_id).first()
            if cat:
                self.company_id = cat.company_id
                self.project_id = cat.project_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Route {self.category_id} -> {self.sla_rule_id}"

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
    def category(self):
        from app.models.core_modules.complaint_management.masters import ComplaintCategory
        if self.category_id:
            return ComplaintCategory.objects.filter(unique_id=self.category_id).first()
        return None

    @property
    def subcategory(self):
        from app.models.core_modules.complaint_management.masters import ComplaintSubcategory
        if self.subcategory_id:
            return ComplaintSubcategory.objects.filter(unique_id=self.subcategory_id).first()
        return None

    @property
    def state(self):
        from app.models.superadmin.common_masters.state import State
        if self.state_id:
            return State.objects.filter(unique_id=self.state_id).first()
        return None

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def ward(self):
        from app.models.masters.ward import Ward
        if self.ward_id:
            return Ward.objects.filter(unique_id=self.ward_id).first()
        return None

    @property
    def priority(self):
        from app.models.core_modules.complaint_management.masters import ComplaintPriority
        if self.priority_id:
            return ComplaintPriority.objects.filter(unique_id=self.priority_id).first()
        return None

    @property
    def user(self):
        from django.conf import settings
        if self.user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.user_id).first()
        return None

    @property
    def sla_rule(self):
        from app.models.core_modules.complaint_management.masters import ComplaintSlaRule
        if self.sla_rule_id:
            return ComplaintSlaRule.objects.filter(unique_id=self.sla_rule_id).first()
        return None


class ComplaintEscalationHistory(BaseMaster):
    """Audit row for each escalation (SLA breach or manual)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_escalation_history_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    escalation_level = models.IntegerField(default=1)
    escalated_to_user_id = models.CharField(max_length=30, null=True, blank=True)
    escalated_to_staff_id = models.CharField(max_length=30, null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    escalated_by_system = models.BooleanField(default=False)

    escalated_at = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_escalation_history_list", "complaint_escalation_history_detail")

    class Meta:
        ordering = ["-escalated_at"]
        verbose_name = "Complaint Escalation History"
        verbose_name_plural = "Complaint Escalation History"

    def __str__(self):
        return f"{self.ticket_id} esc L{self.escalation_level}"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def escalated_to_user(self):
        from django.conf import settings
        if self.escalated_to_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.escalated_to_user_id).first()
        return None

    @property
    def escalated_to_staff(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        if self.escalated_to_staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.escalated_to_staff_id).first()
        return None


class ComplaintFeedback(BaseMaster):
    """Citizen feedback captured after resolution (one per ticket)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_feedback_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    customer_id = models.CharField(max_length=30, null=True, blank=True)
    rating = models.IntegerField(null=True, blank=True)
    feedback_text = models.TextField(blank=True, null=True)
    is_issue_solved = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_feedback_list", "complaint_feedback_detail")

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Complaint Feedback"
        verbose_name_plural = "Complaint Feedback"

    def __str__(self):
        return f"{self.ticket_id} feedback {self.rating}"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def customer(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
        return None


class ComplaintReopenHistory(BaseMaster):
    """Audit row written each time a ticket is reopened."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_reopen_history_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    reopened_by_customer_id = models.CharField(max_length=30, null=True, blank=True)
    reopened_by_user_id = models.CharField(max_length=30, null=True, blank=True)
    reopen_reason = models.TextField(blank=True, null=True)
    previous_status_id = models.CharField(max_length=30, null=True, blank=True)

    reopened_at = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_reopen_history_list", "complaint_reopen_history_detail")

    class Meta:
        ordering = ["-reopened_at"]
        verbose_name = "Complaint Reopen History"
        verbose_name_plural = "Complaint Reopen History"

    def __str__(self):
        return f"{self.ticket_id} reopened"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def reopened_by_customer(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        if self.reopened_by_customer_id:
            return CustomerCreation.objects.filter(unique_id=self.reopened_by_customer_id).first()
        return None

    @property
    def reopened_by_user(self):
        from django.conf import settings
        if self.reopened_by_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.reopened_by_user_id).first()
        return None

    @property
    def previous_status(self):
        from app.models.core_modules.complaint_management.masters import ComplaintStatus
        if self.previous_status_id:
            return ComplaintStatus.objects.filter(unique_id=self.previous_status_id).first()
        return None


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

    ticket_id = models.CharField(max_length=30, null=True, blank=True)
    recipient_staff_id = models.CharField(max_length=30, null=True, blank=True)
    recipient_user_id = models.CharField(max_length=30, null=True, blank=True)

    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, null=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("complaint_notification_list", "complaint_notification_detail")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Complaint Notification"
        verbose_name_plural = "Complaint Notifications"
        indexes = [
            models.Index(fields=["recipient_staff_id", "is_read"]),
            models.Index(fields=["recipient_user_id", "is_read"]),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.ticket_id}"

    @property
    def ticket(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket
        if self.ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.ticket_id).first()
        return None

    @property
    def recipient_staff(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        if self.recipient_staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.recipient_staff_id).first()
        return None

    @property
    def recipient_user(self):
        from django.conf import settings
        if self.recipient_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.recipient_user_id).first()
        return None