from django.db import models
from django.db.models import UniqueConstraint

from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
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

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="userscreen_column_permissions",
        to_field="unique_id",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="userscreen_column_permissions",
        to_field="unique_id",
        db_column="project_id",
        null=True,
        blank=True,
    )
    userscreen_id = models.ForeignKey(
        UserScreen,
        on_delete=models.PROTECT,
        related_name="column_permissions",
        to_field="unique_id",
        db_column="userscreen_id",
    )
    column_id = models.ForeignKey(
        UserScreenColumn,
        on_delete=models.PROTECT,
        related_name="company_permissions",
        to_field="unique_id",
        db_column="column_id",
    )

    can_view = models.BooleanField(default=True)
    order_no = models.IntegerField(default=1)
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
