from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_userscreenaction_id():
    return f"USERSCRNACT-{generate_unique_id()}"


class UserScreenAction(BaseMaster):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_userscreenaction_id,
        editable=False
    )

    action_name = models.CharField(max_length=50, unique=True)
    variable_name = models.CharField(max_length=50, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("companyuserscreenpermissions", "companyuserscreencolumnpermissions", "staff_access_configuration_permissions")
    CACHE_SCOPES = ("user_screen_action_list", "user_screen_action_detail")

    class Meta:
        ordering = ["action_name"]
        verbose_name = "User Screen Action"
        verbose_name_plural = "User Screen Actions"

    def __str__(self):
        return self.action_name

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
    def companyuserscreenpermissions(self):
        from .companyuserscreenpermission import CompanyUserScreenPermission
        return CompanyUserScreenPermission.objects.filter(userscreenaction_id=self.unique_id)

    @property
    def companyuserscreencolumnpermissions(self):
        from .companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
        return CompanyUserScreenColumnPermission.objects.filter(userscreenaction_id=self.unique_id)

    @property
    def staff_access_configuration_permissions(self):
        from app.models.superadmin.staff_management.staff_access_configuration import StaffAccessConfigurationPermission
        return StaffAccessConfigurationPermission.objects.filter(userscreenaction_id=self.unique_id)