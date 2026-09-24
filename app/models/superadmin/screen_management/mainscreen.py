from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .mainscreentype import MainScreenType


def generate_mainscreen_id():
    return f"MAINSCREEN-{generate_unique_id()}"


class MainScreen(BaseMaster):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_mainscreen_id,
        editable=False
    )

    mainscreentype_id = models.CharField(max_length=30, null=True, blank=True)

    mainscreen_name = models.CharField(max_length=50, unique=True)
    icon_name = models.CharField(max_length=50, unique=True)
    order_no = models.IntegerField()

    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("userscreens", "companyuserscreenpermissions")
    CACHE_SCOPES = ("main_screen_list", "main_screen_detail")

    class Meta:
        ordering = ["order_no"]
        verbose_name = "Main Screen"
        verbose_name_plural = "Main Screens"
        constraints = [
            models.UniqueConstraint(
                fields=["mainscreentype_id", "order_no"],
                name="unique_order_per_mainscreentype"
            )
        ]

    def __str__(self):
        return self.mainscreen_name

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
    def mainscreentype(self):
        if self.mainscreentype_id:
            return MainScreenType.objects.filter(unique_id=self.mainscreentype_id).first()
        return None

    @property
    def userscreens(self):
        from .userscreen import UserScreen
        return UserScreen.objects.filter(mainscreen_id=self.unique_id)

    @property
    def companyuserscreenpermissions(self):
        from .companyuserscreenpermission import CompanyUserScreenPermission
        return CompanyUserScreenPermission.objects.filter(mainscreen_id=self.unique_id)