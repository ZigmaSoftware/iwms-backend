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
from app.models.customers.customercreation import CustomerCreation
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
from app.models.complaint_management.masters import (
    ComplaintCategory,
    ComplaintLanguage,
    ComplaintPriority,
    ComplaintSource,
    ComplaintStatus,
    ComplaintSubcategory,
    ComplaintTeam,
)


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

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
        related_name="complaint_tickets",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
        related_name="complaint_tickets",
    )

    source = models.ForeignKey(
        ComplaintSource,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
    )
    wa_phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    profile_name = models.CharField(max_length=150, null=True, blank=True)

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("transgender", "Transgender"),
    ]
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    language = models.ForeignKey(
        ComplaintLanguage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    subcategory = models.ForeignKey(
        ComplaintSubcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        related_name="tickets",
    )

    title = models.CharField(max_length=250, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    location_text = models.TextField(blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Flat geo, mirroring CustomerCreation. `zone`/`ward` are the operational
    # scope the supervisor queues filter on; state/district/panchayat are the
    # administrative rollup kept for reporting.
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="district_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="panchayat_id",
    )
    zone = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="zone_id",
    )
    ward = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="ward_id",
    )

    assigned_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaint_tickets",
    )
    assigned_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaint_tickets_staff",
    )

    sla_due_at = models.DateTimeField(null=True, blank=True)
    first_response_due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    sla_breached = models.BooleanField(default=False)
    sla_breached_at = models.DateTimeField(null=True, blank=True)

    reopened_count = models.IntegerField(default=0)
    parent_ticket = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_tickets",
    )
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
            models.Index(fields=["sla_due_at"]),
        ]

    def __str__(self):
        return self.ticket_no
