from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_usertype_id():
    return f"UTYPE-{generate_unique_id()}"


class UserType(BaseMaster):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_usertype_id,
        editable=False
    )

    name = models.CharField(
        max_length=50,
        unique=True
    )

    CASCADE_SOFT_DELETE = ("staff_users", "customer_users")
    CACHE_SCOPES = ("user_type_list", "user_type_detail")

    class Meta:
        ordering = ["name"]
        verbose_name = "User Type"
        verbose_name_plural = "User Types"

    def __str__(self):
        return self.name

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

    @property
    def staff_users(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        return StaffcreationOfficeDetails.objects.filter(user_type_id=self.unique_id)

    @property
    def customer_users(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        return CustomerCreation.objects.filter(user_type_id=self.unique_id)