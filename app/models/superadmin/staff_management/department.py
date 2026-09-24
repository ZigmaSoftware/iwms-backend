from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_department_id():
    return f"DEPT-{generate_unique_id()}"


class Department(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_department_id,
        editable=False,
    )
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    department_name = models.CharField(max_length=150)
    department_code = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("staff_members", "designations")
    CACHE_SCOPES = ("department_list", "department_detail")

    class Meta:
        ordering = ["department_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "project_id", "department_code"],
                name="unique_department_code_per_project",
            )
        ]

    def __str__(self):
        return self.department_name

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
    def staff_members(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        return StaffcreationOfficeDetails.objects.filter(department_id=self.unique_id)

    @property
    def designations(self):
        from app.models.superadmin.staff_management.designation import Designation
        return Designation.objects.filter(department_id=self.unique_id)