"""Complaint ticket, ported from the government backend.

Geo is the one place this deliberately diverges from government. The
government ticket carries State/District/AreaType plus five mutually
exclusive local-body FKs (Corporation/Municipality/TownPanchayat/
PanchayatUnion/Panchayat). This project dropped AreaType, Corporation,
Municipality and TownPanchayat entirely, and scopes operational data by
Company/Project + Zone/Ward instead, so the ticket inherits the same geo
shape as `CustomerCreation`: state -> district -> panchayat, plus zone/ward
and the company/project tenancy pair.
"""

from django.conf import settings
from django.db import models
from django.db.models import Max

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_ticket_unique_id():
    return f"CPTTKT-{generate_unique_id()}"


def generate_ticket_no():
    """Sequential ticket number IWMS-<seq:06d> based on max existing ticket_no."""
    last = ComplaintTicket.objects.aggregate(max_no=Max("ticket_no"))["max_no"]
    last_num = 0
    if last:
        try:
            last_num = int(str(last).split("-")[-1])
        except (ValueError, IndexError):
            last_num = 0
    return f"IWMS-{last_num + 1:06d}"


class ComplaintTicket(BaseMaster):
    """Main complaint ticket. Citizen = CustomerCreation; geo follows this
    project's Zone/Ward-under-Company/Project model."""

    # status_history/assignment_history/escalation_history/reopen_history/
    # comments/notifications are kept as a permanent record even after the
    # ticket itself is soft-deleted, so they are deliberately excluded here.
    CASCADE_SOFT_DELETE = (
        "child_tickets",
        "extra_details",
        "attachments",
        "feedback",
        "address_change_request",
    )
    CACHE_SCOPES = ("complaint_ticket_list", "complaint_ticket_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_ticket_unique_id,
        editable=False,
    )
    ticket_no = models.CharField(
        max_length=50,
        unique=True,
        default=generate_ticket_no,
        editable=False,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    source_id = models.CharField(max_length=30, null=True, blank=True)
    customer_id = models.CharField(max_length=30, null=True, blank=True)
    wa_phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    profile_name = models.CharField(max_length=150, null=True, blank=True)

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("transgender", "Transgender"),
    ]
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    language_id = models.CharField(max_length=30, null=True, blank=True)

    category_id = models.CharField(max_length=30, null=True, blank=True)
    subcategory_id = models.CharField(max_length=30, null=True, blank=True)
    priority_id = models.CharField(max_length=30, null=True, blank=True)
    status_id = models.CharField(max_length=30, null=True, blank=True)

    title = models.CharField(max_length=250, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    location_text = models.TextField(blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Flat geo, mirroring CustomerCreation. `zone`/`ward` are the operational
    # scope the supervisor queues filter on; state/district/panchayat are the
    # administrative rollup kept for reporting.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)

    assigned_user_id = models.CharField(max_length=30, null=True, blank=True)
    assigned_staff_id = models.CharField(max_length=30, null=True, blank=True)
    is_escalated = models.BooleanField(default=False)
    escalated_to_staff_id = models.CharField(max_length=30, null=True, blank=True)
    escalation_level = models.PositiveIntegerField(
        default=0,
        help_text="Current hop in the project's staff hierarchy (0 = first assignee, matches ProjectStaffHierarchy.level).",
    )
    next_escalation_due_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Deadline for the current escalation_level. If passed and unresolved, auto-escalate to the next hierarchy level.",
    )

    first_response_due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    reopened_count = models.IntegerField(default=0)
    parent_ticket_id = models.CharField(max_length=30, null=True, blank=True)
    idempotency_key = models.CharField(max_length=150, db_index=True, null=True, blank=True)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Ticket"
        verbose_name_plural = "Complaint Tickets"
        indexes = [
            models.Index(fields=["ticket_no"]),
            models.Index(fields=["wa_phone"]),
            models.Index(fields=["next_escalation_due_at"]),
        ]

    def __str__(self):
        return self.ticket_no

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
    def source(self):
        from app.models.complaint_management.masters import ComplaintSource
        if self.source_id:
            return ComplaintSource.objects.filter(unique_id=self.source_id).first()
        return None

    @property
    def customer(self):
        from app.models.customers.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
        return None

    @property
    def language(self):
        from app.models.complaint_management.masters import ComplaintLanguage
        if self.language_id:
            return ComplaintLanguage.objects.filter(unique_id=self.language_id).first()
        return None

    @property
    def category(self):
        from app.models.complaint_management.masters import ComplaintCategory
        if self.category_id:
            return ComplaintCategory.objects.filter(unique_id=self.category_id).first()
        return None

    @property
    def subcategory(self):
        from app.models.complaint_management.masters import ComplaintSubcategory
        if self.subcategory_id:
            return ComplaintSubcategory.objects.filter(unique_id=self.subcategory_id).first()
        return None

    @property
    def priority(self):
        from app.models.complaint_management.masters import ComplaintPriority
        if self.priority_id:
            return ComplaintPriority.objects.filter(unique_id=self.priority_id).first()
        return None

    @property
    def status(self):
        from app.models.complaint_management.masters import ComplaintStatus
        if self.status_id:
            return ComplaintStatus.objects.filter(unique_id=self.status_id).first()
        return None

    @property
    def state(self):
        from app.models.common_masters.state import State
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
    def assigned_user(self):
        from django.conf import settings
        if self.assigned_user_id:
            return settings.AUTH_USER_MODEL.objects.filter(unique_id=self.assigned_user_id).first()
        return None

    @property
    def assigned_staff(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.assigned_staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.assigned_staff_id).first()
        return None

    @property
    def escalated_to_staff(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.escalated_to_staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.escalated_to_staff_id).first()
        return None

    @property
    def parent_ticket(self):
        if self.parent_ticket_id:
            return ComplaintTicket.objects.filter(unique_id=self.parent_ticket_id).first()
        return None