from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .userType import UserType


def generate_staff_usertype_id():
    return f"STUSRTYPE-{generate_unique_id()}"


class StaffUserType(BaseMaster):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    STAFF_ROLE_CHOICES = [
        ("company_admin", "Company Admin"),
        ("company_operator", "Company Operator"),
        ("company_driver", "Company Driver"),
        ("company_supervisor", "Company Supervisor"),
        ("company_user", "Company User"),
        ("company_project_admin", "Company Project Admin"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_staff_usertype_id,
        editable=False
    )

    usertype_id = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(
        max_length=50,
        choices=STAFF_ROLE_CHOICES
    )

    CASCADE_SOFT_DELETE = ("staff_users",)
    CACHE_SCOPES = ("staff_user_type_list", "staff_user_type_detail")

    class Meta:
        ordering = ["name"]
        verbose_name = "Staff User Type"
        verbose_name_plural = "Staff User Types"
        constraints = [
            models.UniqueConstraint(
                fields=["usertype_id", "name", "is_deleted"],
                name="unique_staff_role_per_usertype_not_deleted"
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
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        return StaffcreationOfficeDetails.objects.filter(staffusertype_id=self.unique_id)
