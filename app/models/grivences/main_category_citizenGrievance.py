from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_maincategory_id():
    return f"CMPMC-{generate_unique_id()}"

class MainCategory(BaseMaster):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_maincategory_id,
        editable=False
    )

    main_categoryName = models.CharField(
        max_length=100,
        unique=True,
    )

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Main Category"
        verbose_name_plural = "Main Categories"

    def __str__(self):
        return self.main_categoryName

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

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
