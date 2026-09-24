from django.db import models
from django.db.models import UniqueConstraint

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_companyuserscreencolumnpermission_id():
    return f"CMPUSERSCRNCOLPERM-{generate_unique_id()}"


class CompanyUserScreenColumnPermission(BaseMaster):
    unique_id = models.CharField(
        max_length=70,
        primary_key=True,
        unique=True,
        default=generate_companyuserscreencolumnpermission_id,
        editable=False,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    userscreen_id = models.CharField(max_length=30, null=True, blank=True)
    column_id = models.CharField(max_length=40, null=True, blank=True)

    can_view = models.BooleanField(default=True)
    order_no = models.IntegerField(default=1)
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("company_user_screen_column_permission_list", "company_user_screen_column_permission_detail")

    class Meta:
        ordering = ["order_no"]
        verbose_name = "Company User Screen Column Permission"
        verbose_name_plural = "Company User Screen Column Permissions"
        indexes = [
            models.Index(fields=["company_id", "project_id", "userscreen_id"]),
            models.Index(fields=["userscreen_id", "column_id", "is_active", "is_deleted"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=[
                    "company_id",
                    "project_id",
                    "userscreen_id",
                    "column_id",
                    "is_deleted",
                ],
                name="uq_company_project_screen_column_perm",
            )
        ]

    @property
    def userscreencolumn_id(self):
        return self.column_id

    def __str__(self):
        return f"{self.company_id} - {self.userscreen_id} - {self.column_id}"

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
    def userscreen(self):
        from .userscreen import UserScreen
        if self.userscreen_id:
            return UserScreen.objects.filter(unique_id=self.userscreen_id).first()
        return None

    @property
    def column(self):
        from .userscreencolumn import UserScreenColumn
        if self.column_id:
            return UserScreenColumn.objects.filter(unique_id=self.column_id).first()
        return None