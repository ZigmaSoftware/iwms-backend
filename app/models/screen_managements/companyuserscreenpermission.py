from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from django.db.models import Q, UniqueConstraint


def generate_companyuserscreenpermission_id():
    return f"CMPUSERSCRNPERM-{generate_unique_id()}"


class PermissionType(models.TextChoices):
    SCREEN = "screen", "Screen Permission"
    FIELD = "field", "Field Permission"


class CompanyUserScreenPermission(BaseMaster):
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_companyuserscreenpermission_id,
        editable=False
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    mainscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreenaction_id = models.CharField(max_length=30, null=True, blank=True)

    permission_type = models.CharField(
        max_length=20,
        choices=PermissionType.choices,
        default=PermissionType.SCREEN,
    )

    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    city_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)

    order_no = models.IntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("companyuserscreencolumnpermissions",)
    CACHE_SCOPES = ("company_user_screen_permission_list", "company_user_screen_permission_detail")

    class Meta:
        ordering = ["order_no"]
        indexes = [
            models.Index(
                fields=["company_id", "project_id", "mainscreen_id", "permission_type"],
                name="app_company_company_9c08d3_idx",
            ),
        ]
        constraints = [
            UniqueConstraint(
                fields=[
                    "company_id",
                    "project_id",
                    "mainscreen_id",
                    "permission_type",
                    "userscreen_id",
                    "userscreenaction_id",
                ],
                condition=Q(is_deleted=False),
                name="uq_active_company_project_screen_perm_type",
            )
        ]


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
    def mainscreen(self):
        from .mainscreen import MainScreen
        if self.mainscreen_id:
            return MainScreen.objects.filter(unique_id=self.mainscreen_id).first()
        return None

    @property
    def userscreen(self):
        from .userscreen import UserScreen
        if self.userscreen_id:
            return UserScreen.objects.filter(unique_id=self.userscreen_id).first()
        return None

    @property
    def userscreenaction(self):
        from .userscreenaction import UserScreenAction
        if self.userscreenaction_id:
            return UserScreenAction.objects.filter(unique_id=self.userscreenaction_id).first()
        return None

    @property
    def state(self):
        from app.models.common_masters.state import State
        if self.state_id:
            return State.objects.filter(unique_id=self.state_id).first()
        return None

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

    @property
    def city(self):
        from app.models.masters.city import City
        if self.city_id:
            return City.objects.filter(unique_id=self.city_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def ward(self):
        from app.models.masters.ward import Ward
        if self.ward_id:
            return Ward.objects.filter(unique_id=self.ward_id).first()
        return None

    @property
    def companyuserscreencolumnpermissions(self):
        from .companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
        return CompanyUserScreenColumnPermission.objects.filter(userscreen_id=self.unique_id)