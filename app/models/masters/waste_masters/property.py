from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id



def generate_propertyName_id():
    return f"PROPERTY-{generate_unique_id()}"


class Property(BaseMaster):

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,               
        unique=True,
        default=generate_propertyName_id,
        editable=False
    )

    property_name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Fuel Type"
        verbose_name_plural = "Fuel Types"
        ordering = ["property_name"]

    def __str__(self):
        return self.property_name

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