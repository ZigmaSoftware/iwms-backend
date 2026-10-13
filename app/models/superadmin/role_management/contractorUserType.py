from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .userType import UserType


def generate_contractor_usertype_id():
    return f"CNTUSRTYPE-{generate_unique_id()}"


class ContractorUserType(BaseMaster):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    CONTRACTOR_ROLE_CHOICES = [
        ("contractor_admin", "Contractor Admin"),
        ("contractor_supervisor", "Contractor Supervisor"),
        ("contractor_operator", "Contractor Operator"),
        ("contractor_worker", "Contractor Worker"),
        ("contractor_driver", "Contractor Driver"),
    ]

    unique_id = models.CharField(
        max_length=35,
        primary_key=True,
        unique=True,
        default=generate_contractor_usertype_id,
        editable=False,
    )

    usertype_id = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(
        max_length=50,
        choices=CONTRACTOR_ROLE_CHOICES,
    )

    CASCADE_SOFT_DELETE = ("staff_users",)
    CACHE_SCOPES = ("contractor_user_type_list", "contractor_user_type_detail")

    class Meta:
        ordering = ["name"]
        verbose_name = "Contractor User Type"
        verbose_name_plural = "Contractor User Types"
        constraints = [
            models.UniqueConstraint(
                fields=["usertype_id", "name", "is_deleted"],
                name="unique_contractor_role_per_usertype_not_deleted",
            )
        ]

    def __str__(self):
        return f"{self.usertype_id} → {self.name}"

    def save(self, *args, **kwargs):
        if self.usertype_id is not None and hasattr(self.usertype_id, "unique_id"):
            self.usertype_id = self.usertype_id.unique_id
        elif self.usertype_id:
            usertype = UserType.objects.filter(name__iexact=str(self.usertype_id).strip()).first()
            if usertype:
                self.usertype_id = usertype.unique_id
        super().save(*args, **kwargs)

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
    def usertype(self):
        if self.usertype_id:
            return UserType.objects.filter(unique_id=self.usertype_id).first()
        return None

    @property
    def staff_users(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        return StaffcreationOfficeDetails.objects.filter(contractorusertype_id=self.unique_id)
