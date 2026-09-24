from django.db import models
from django.core.exceptions import ValidationError

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .staffUserType import StaffUserType


def generate_project_staff_hierarchy_id():
    return f"PSHIER-{generate_unique_id()}"


class ProjectStaffHierarchy(BaseMaster):
    """Per-project reporting chain between Staff User Types.

    Each row says: within this project, staff of `staffusertype_id` report
    up to staff of `reports_to_staffusertype_id`. The chain can differ
    project to project — one project may skip a level another project uses.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_project_staff_hierarchy_id,
        editable=False,
    )

    project_id = models.CharField(max_length=30, null=True, blank=True)

    staffusertype_id = models.CharField(max_length=30, null=True, blank=True)

    reports_to_staffusertype_id = models.CharField(max_length=30, null=True, blank=True,
        help_text="Left blank for the top of the chain (e.g. Company Admin).",
    )

    level = models.PositiveIntegerField(
        help_text="Display/ordering rank within the project (1 = lowest level).",
    )

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("project_staff_hierarchy_list", "project_staff_hierarchy_detail")

    class Meta:
        ordering = ["project_id", "level"]
        verbose_name = "Project Staff Hierarchy"
        verbose_name_plural = "Project Staff Hierarchies"
        constraints = [
            models.UniqueConstraint(
                fields=["project_id", "staffusertype_id", "is_deleted"],
                name="unique_staffusertype_per_project_not_deleted",
            )
        ]

    def __str__(self):
        reports_to = ""
        if self.reports_to_staffusertype_id:
            from .staffUserType import StaffUserType
            st = StaffUserType.objects.filter(unique_id=self.reports_to_staffusertype_id).first()
            if st:
                reports_to = st.name
        else:
            reports_to = "—"
        return f"{self.project_id}: {self.staffusertype_id} → {reports_to}"

    def clean(self):
        if self.reports_to_staffusertype_id == self.staffusertype_id:
            raise ValidationError("A staff user type cannot report to itself.")

        if self.reports_to_staffusertype_id:
            seen = {self.staffusertype_id}
            current = self.reports_to_staffusertype_id
            while current is not None:
                if current in seen:
                    raise ValidationError("This mapping creates a reporting cycle.")
                seen.add(current)
                from app.models.role_assigns.projectStaffHierarchy import ProjectStaffHierarchy
                next_entry = (
                    ProjectStaffHierarchy.objects.filter(
                        project_id=self.project_id,
                        staffusertype_id=current,
                        is_deleted=False,
                    )
                    .exclude(pk=self.pk)
                    .first()
                )
                current = next_entry.reports_to_staffusertype_id if next_entry else None

    @property
    def project(self):
        from app.models.superadmin_masters.project import Project
        if self.project_id:
            return Project.objects.filter(unique_id=self.project_id).first()
        return None

    @property
    def staffusertype(self):
        from .staffUserType import StaffUserType
        if self.staffusertype_id:
            return StaffUserType.objects.filter(unique_id=self.staffusertype_id).first()
        return None

    @property
    def reports_to_staffusertype(self):
        from .staffUserType import StaffUserType
        if self.reports_to_staffusertype_id:
            return StaffUserType.objects.filter(unique_id=self.reports_to_staffusertype_id).first()
        return None