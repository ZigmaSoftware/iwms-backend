from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from django.db.models import Q, UniqueConstraint

from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward


def generate_companyuserscreenpermission_id():
    return f"CMPUSERSCRNPERM-{generate_unique_id()}"


class PermissionType(models.TextChoices):
    SCREEN = "screen", "Screen Permission"
    FIELD = "field", "Field Permission"


class CompanyUserScreenPermission(BaseMaster):
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_companyuserscreenpermission_id,
        editable=False
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        to_field="unique_id", db_column="company_id",
        related_name="userscreenpermissions"
    )
    mainscreen_id = models.ForeignKey(
        MainScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="mainscreen_id",
        related_name="userscreenpermissions"
    )

    userscreen_id = models.ForeignKey(
        UserScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreen_id",
        related_name="userscreenpermissions"
    )

    userscreenaction_id = models.ForeignKey(
        UserScreenAction, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreenaction_id",
        related_name="userscreenpermissions"
    )

    permission_type = models.CharField(
        max_length=20,
        choices=PermissionType.choices,
        default=PermissionType.SCREEN,
    )

    state_id = models.ForeignKey(
        State, on_delete=models.PROTECT,
        db_column="state_id", null=True, blank=True,
        related_name="userscreenpermissions"
    )
    district_id = models.ForeignKey(
        District, on_delete=models.PROTECT,
        db_column="district_id", null=True, blank=True,
        related_name="userscreenpermissions"
    )
    city_id = models.ForeignKey(
        City, on_delete=models.PROTECT,
        db_column="city_id", null=True, blank=True,
        related_name="userscreenpermissions"
    )
    zone_id = models.ForeignKey(
        Zone, on_delete=models.PROTECT,
        db_column="zone_id", null=True, blank=True,
        related_name="userscreenpermissions"
    )
    panchayat_id = models.ForeignKey(
        Panchayat, on_delete=models.PROTECT,
        db_column="panchayat_id", null=True, blank=True,
        related_name="userscreenpermissions"
    )
    ward_id = models.ForeignKey(
        Ward, on_delete=models.PROTECT,
        db_column="ward_id", null=True, blank=True,
        related_name="userscreenpermissions"
    )

    order_no = models.IntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
