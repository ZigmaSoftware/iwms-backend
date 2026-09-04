"""Complaint/grievance master tables.

Ported from the government backend's `core_modules/complaint_management`
masters. These are geo-agnostic, so they carry over unchanged apart from
living under `app.models.complaint_management` to match this project's flat
model layout.
"""

from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.staff_creations.department import Department
from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails


def generate_source_id():
    return f"CPTSRC-{generate_unique_id()}"


def generate_language_id():
    return f"CPTLANG-{generate_unique_id()}"


def generate_priority_id():
    return f"CPTPRI-{generate_unique_id()}"


def generate_status_id():
    return f"CPTSTAT-{generate_unique_id()}"


def generate_module_id():
    return f"CPTMOD-{generate_unique_id()}"


def generate_category_id():
    return f"CPTCAT-{generate_unique_id()}"


def generate_subcategory_id():
    return f"CPTSUB-{generate_unique_id()}"


def generate_team_id():
    return f"CPTTEAM-{generate_unique_id()}"


def generate_sla_rule_id():
    return f"CPTSLA-{generate_unique_id()}"


class ComplaintSource(BaseMaster):
    """Where a complaint ticket came from: WhatsApp, Mobile App, Web, Call Center, Admin."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_source_id,
        editable=False,
    )

    source_code = models.CharField(max_length=50, unique=True)
    source_name = models.CharField(max_length=100)

    class Meta:
        ordering = ["source_code"]
        verbose_name = "Complaint Source"
        verbose_name_plural = "Complaint Sources"

    def __str__(self):
        return self.source_name


class ComplaintLanguage(BaseMaster):
    """Citizen-facing languages: en, hi, ta, te."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_language_id,
        editable=False,
    )

    language_code = models.CharField(max_length=20, unique=True)
    language_name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["language_code"]
        verbose_name = "Complaint Language"
        verbose_name_plural = "Complaint Languages"

    def __str__(self):
        return self.language_name


class ComplaintPriority(BaseMaster):
    """Priority levels: P1 Emergency, P2 High, P3 Normal, P4 Info."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_priority_id,
        editable=False,
    )

    priority_code = models.CharField(max_length=20, unique=True)
    priority_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Priority"
        verbose_name_plural = "Complaint Priorities"

    def __str__(self):
        return self.priority_name


class ComplaintStatus(BaseMaster):
    """Ticket lifecycle statuses: SUBMITTED, ASSIGNED, IN_PROGRESS, RESOLVED, ..."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_status_id,
        editable=False,
    )

    status_code = models.CharField(max_length=50, unique=True)
    status_name = models.CharField(max_length=100)
    is_final = models.BooleanField(default=False)
    allow_reopen = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Status"
        verbose_name_plural = "Complaint Statuses"

    def __str__(self):
        return self.status_name


class ComplaintModule(BaseMaster):
    """Top-level business module a complaint category belongs to (Assets, Transport, ...)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_module_id,
        editable=False,
    )

    module_code = models.CharField(max_length=80, unique=True)
    module_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Module"
        verbose_name_plural = "Complaint Modules"

    def __str__(self):
        return self.module_name


class ComplaintTeam(BaseMaster):
    """Teams that complaint tickets are routed/assigned to."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_team_id,
        editable=False,
    )

    team_code = models.CharField(max_length=80, unique=True)
    team_name = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_teams",
    )
    lead_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_complaint_teams",
    )
    escalates_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_sources",
    )
    escalation_level = models.IntegerField(default=1)
    is_field_team = models.BooleanField(default=False)

    class Meta:
        ordering = ["team_code"]
        verbose_name = "Complaint Team"
        verbose_name_plural = "Complaint Teams"

    def __str__(self):
        return self.team_name


class ComplaintCategory(BaseMaster):
    """Top-level complaint categories (Missed Pickup, Change Address, ...)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_category_id,
        editable=False,
    )

    module = models.ForeignKey(
        ComplaintModule,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="categories",
    )
    category_code = models.CharField(max_length=80, unique=True)
    category_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    default_priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="default_for_categories",
    )
    default_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_categories",
    )

    requires_location = models.BooleanField(default=True)
    requires_media = models.BooleanField(default=False)
    requires_address_change_detail = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Category"
        verbose_name_plural = "Complaint Categories"

    def __str__(self):
        return self.category_name


class ComplaintSubcategory(BaseMaster):
    """Subcategories under a complaint category."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_subcategory_id,
        editable=False,
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="subcategories",
    )
    subcategory_code = models.CharField(max_length=80)
    subcategory_name = models.CharField(max_length=150)
    default_priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_subcategories",
    )
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Subcategory"
        verbose_name_plural = "Complaint Subcategories"
        unique_together = ("category", "subcategory_code")

    def __str__(self):
        return self.subcategory_name


class ComplaintSlaRule(BaseMaster):
    """Configurable assign/resolve SLA + escalation per category/priority/source."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_sla_rule_id,
        editable=False,
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="sla_rules",
    )
    subcategory = models.ForeignKey(
        ComplaintSubcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sla_rules",
    )
    priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.PROTECT,
        related_name="sla_rules",
    )
    source = models.ForeignKey(
        ComplaintSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sla_rules",
    )

    assign_within_minutes = models.IntegerField(null=True, blank=True)
    resolve_within_minutes = models.IntegerField(null=True, blank=True)
    working_hours_only = models.BooleanField(default=False)
    escalation_after_minutes = models.IntegerField(null=True, blank=True)
    escalation_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_sla_rules",
    )

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint SLA Rule"
        verbose_name_plural = "Complaint SLA Rules"

    def __str__(self):
        return f"SLA {self.category_id} / {self.priority_id}"
