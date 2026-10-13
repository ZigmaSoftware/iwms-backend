from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id



def generate_subcategory_id():
    return f"CMPSC-{generate_unique_id()}"


class SubCategory(BaseMaster):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_subcategory_id,
        editable=False,
    )

    mainCategory = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(max_length=120)
    class Meta:
        ordering = ["unique_id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])

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
    def mainCategory_obj(self):
        from app.models.core_modules.complaint_management.main_category_citizenGrievance import MainCategory
        if self.mainCategory:
            return MainCategory.objects.filter(unique_id=self.mainCategory).first()
        return None
