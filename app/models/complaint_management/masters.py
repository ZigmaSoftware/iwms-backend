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
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


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


def generate_sla_rule_id():
    return f"CPTSLA-{generate_unique_id()}"


def generate_department_member_id():
    # Kept only because migration 0003 references it as a field default
    # callable; ComplaintDepartmentMember itself was removed in migration
    # 0006 (hierarchy-based ticket assignment replaced department routing).
    return f"CPTDM-{generate_unique_id()}"


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


class ComplaintCategory(BaseMaster):
    """Top-level complaint categories (Missed Pickup, Change Address, ...).

    Scoped to a company/project: the categories a citizen is offered, their
    default priority and the department they route to are all operational
    choices that differ per project, so one project's edit must not change
    another's.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_category_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="complaint_categories",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="complaint_categories",
        db_column="project_id",
        null=True,
        blank=True,
    )

    module = models.ForeignKey(
        ComplaintModule,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="categories",
    )
    category_code = models.CharField(max_length=80)
    category_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    default_priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="default_for_categories",
    )
    default_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_complaint_categories",
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
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "project_id", "category_code"],
                name="unique_complaint_category_code_per_project",
            )
        ]

    def __str__(self):
        return self.category_name


class ComplaintSubcategory(BaseMaster):
    """Subcategories under a complaint category.

    Carries the same company/project as its parent category — denormalised so
    the list can be filtered without a join, and stamped from the category on
    save so the two can never disagree.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_subcategory_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="complaint_subcategories",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="complaint_subcategories",
        db_column="project_id",
        null=True,
        blank=True,
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

    def save(self, *args, **kwargs):
        # A subcategory belongs to exactly one category, so its tenancy is
        # never an independent choice — always take it from the parent.
        if self.category_id:
            self.company_id_id = self.category.company_id_id
            self.project_id_id = self.category.project_id_id
        super().save(*args, **kwargs)

    def __str__(self):
        return self.subcategory_name


class ComplaintSlaRule(BaseMaster):
    """Configurable assign/resolve SLA + escalation per category/priority/source.

    Scoped like its category: resolution targets are a per-project commitment,
    so one project's SLA must not bind another's.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_sla_rule_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="complaint_sla_rules",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="complaint_sla_rules",
        db_column="project_id",
        null=True,
        blank=True,
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
    working_hours_only = models.BooleanField(default=False)
    # DEPRECATED: superseded by ComplaintSlaEscalationLevel, which gives each
    # hierarchy hop its own window instead of one fixed value for all of them.
    escalation_after_minutes = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint SLA Rule"
        verbose_name_plural = "Complaint SLA Rules"

    def save(self, *args, **kwargs):
        # Same reasoning as ComplaintSubcategory: tenancy follows the category.
        if self.category_id:
            self.company_id_id = self.category.company_id_id
            self.project_id_id = self.category.project_id_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"SLA {self.category_id} / {self.priority_id}"


def generate_sla_escalation_level_id():
    return f"CPTSLAL-{generate_unique_id()}"


class ComplaintSlaEscalationLevel(BaseMaster):
    """Resolution window for one hop of a project's staff hierarchy.

    `level` matches `ProjectStaffHierarchy.level` for the ticket's project.
    Only `is_enabled` rows participate in escalation: a ticket is first
    assigned to the lowest-numbered enabled level's staff, and on breach hops
    to the next enabled level above it — disabled levels (e.g. Driver,
    Operator) are skipped entirely, both as an entry point and as a hop
    target. Kept as its own table (not fixed l1/l2/l3 columns) because
    hierarchy depth is configured per project and can vary.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_sla_escalation_level_id,
        editable=False,
    )

    sla_rule = models.ForeignKey(
        ComplaintSlaRule,
        on_delete=models.CASCADE,
        related_name="escalation_levels",
    )
    level = models.PositiveIntegerField(
        help_text="Hierarchy level this window applies to (matches ProjectStaffHierarchy.level).",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether this hierarchy level participates in escalation for this SLA rule.",
    )
    resolve_within_minutes = models.IntegerField(
        help_text="Minutes this level has to resolve the ticket before it escalates further.",
    )

    class Meta:
        ordering = ["sla_rule", "level"]
        verbose_name = "Complaint SLA Escalation Level"
        verbose_name_plural = "Complaint SLA Escalation Levels"
        constraints = [
            models.UniqueConstraint(
                fields=["sla_rule", "level"],
                condition=models.Q(is_deleted=False),
                name="unique_sla_escalation_level_per_rule",
            )
        ]

    def __str__(self):
        return f"{self.sla_rule_id} L{self.level}: {self.resolve_within_minutes}m"
