from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_designation_id():
    return f"DESG-{generate_unique_id()}"


class Designation(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_designation_id,
        editable=False,
    )
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    department_id = models.CharField(max_length=30, null=True, blank=True)
    designation_name = models.CharField(max_length=150)
    designation_group = models.CharField(max_length=80, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("staff_members",)
    CACHE_SCOPES = ("designation_list", "designation_detail")

    class Meta:
        ordering = ["designation_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "project_id", "designation_name", "department_id"],
                name="unique_designation_per_project_department",
            )
        ]

    def __str__(self):
        return self.designation_name

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
    def department(self):
        from app.models.staff_creations.department import Department
        if self.department_id:
            return Department.objects.filter(unique_id=self.department_id).first()
        return None

    @property
    def staff_members(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        return StaffcreationOfficeDetails.objects.filter(designation_id=self.unique_id)