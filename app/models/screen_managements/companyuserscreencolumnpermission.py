from django.db import models
from django.db.models import Q, UniqueConstraint

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.screen_managements.userscreencolumn import UserScreenColumn


def generate_companyuserscreencolumnpermission_id():
    return f"CMPUSERSCRNCOLPERM-{generate_unique_id()}"


class CompanyUserScreenColumnPermission(BaseMaster):
    """
    Column-level permissions for UserScreens.
    Links CompanyUserScreenPermission (which handles action-level permissions)
    to specific UserScreenColumn for granular column access control.
    """

    unique_id = models.CharField(
        max_length=70,
        primary_key=True,
        unique=True,
        default=generate_companyuserscreencolumnpermission_id,
        editable=False
    )

    # Link to the parent action permission
    companyuserscreenpermission_id = models.ForeignKey(
        CompanyUserScreenPermission,
        on_delete=models.CASCADE,
        related_name="column_permissions",
        to_field="unique_id",
        db_column="companyuserscreenpermission_id",
        help_text="Parent action permission this column permission belongs to"
    )

    # Link to the specific column
    userscreencolumn_id = models.ForeignKey(
        UserScreenColumn,
        on_delete=models.CASCADE,
        related_name="company_permissions",
        to_field="unique_id",
        db_column="userscreencolumn_id",
        help_text="The specific column this permission applies to"
    )

    # Permission flags for this column
    can_view = models.BooleanField(
        default=True,
        help_text="Whether the user can view this column's data"
    )

    can_edit = models.BooleanField(
        default=False,
        help_text="Whether the user can edit this column's data"
    )

    can_filter = models.BooleanField(
        default=True,
        help_text="Whether the user can filter by this column"
    )

    can_search = models.BooleanField(
        default=True,
        help_text="Whether the user can search within this column"
    )

    can_sort = models.BooleanField(
        default=True,
        help_text="Whether the user can sort by this column"
    )

    # Ordering
    order_no = models.IntegerField(
        default=1,
        help_text="Display order for this column permission"
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional description for this column permission"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company User Screen Column Permission"
        verbose_name_plural = "Company User Screen Column Permissions"

        # Ensure unique combination of permission + column
        constraints = [
            UniqueConstraint(
                fields=["companyuserscreenpermission_id", "userscreencolumn_id"],
                condition=Q(is_deleted=False),
                name="unique_company_screen_column_permission"
            ),
            models.Index(
                fields=[
                    "companyuserscreenpermission_id",
                    "userscreencolumn_id",
                    "is_deleted",
                    "is_active"
                ],
                name="idx_company_column_perm_active"
            ),
        ]

    def __str__(self):
        return f"{self.companyuserscreenpermission_id} - {self.userscreencolumn_id.column_name}"

    def delete(self, *args, **kwargs):
        """Soft delete"""
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

    # Helper properties
    @property
    def company_id(self):
        """Get company from parent permission"""
        return self.companyuserscreenpermission_id.company_id

    @property
    def userscreen_id(self):
        """Get userscreen from parent permission"""
        return self.companyuserscreenpermission_id.userscreen_id

    @property
    def userscreenaction_id(self):
        """Get action from parent permission"""
        return self.companyuserscreenpermission_id.userscreenaction_id</content>
<parameter name="filePath">iwms-backend/app/models/screen_managements/companyuserscreencolumnpermission.py