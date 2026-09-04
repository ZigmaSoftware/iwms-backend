from django.db import models
from django.db.models import UniqueConstraint

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id

from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction


def generate_staff_access_configuration_id():
    return f"STFACCCFG-{generate_unique_id()}"


class StaffAccessConfiguration(BaseMaster):
    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_staff_access_configuration_id,
        editable=False,
    )

    staff_id = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.CASCADE,
        to_field="staff_unique_id",
        db_column="staff_id",
        related_name="access_configuration",
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="company_id",
        related_name="staff_access_configurations",
    )

    projects = models.ManyToManyField(
        Project,
        related_name="staff_access_configurations",
        blank=True,
    )

    states = models.ManyToManyField(
        State, related_name="staff_access_configurations", blank=True,
    )
    districts = models.ManyToManyField(
        District, related_name="staff_access_configurations", blank=True,
    )
    cities = models.ManyToManyField(
        City, related_name="staff_access_configurations", blank=True,
    )
    zones = models.ManyToManyField(
        Zone, related_name="staff_access_configurations", blank=True,
    )
    panchayats = models.ManyToManyField(
        Panchayat, related_name="staff_access_configurations", blank=True,
    )
    wards = models.ManyToManyField(
        Ward, related_name="staff_access_configurations", blank=True,
    )

    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            UniqueConstraint(
                fields=["staff_id"],
                condition=models.Q(is_deleted=False),
                name="uq_active_staff_access_configuration",
            )
        ]

    def __str__(self):
        return f"{self.staff_id_id}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])


def generate_staff_access_configuration_permission_id():
    return f"STFACCCFGPERM-{generate_unique_id()}"


class StaffAccessConfigurationPermission(BaseMaster):
    """A single screen+action grant belonging to a StaffAccessConfiguration.

    Scope (company/project/location) is inherited from the parent
    StaffAccessConfiguration row, not duplicated here.
    """

    unique_id = models.CharField(
        max_length=70,
        primary_key=True,
        unique=True,
        default=generate_staff_access_configuration_permission_id,
        editable=False,
    )

    staff_access_configuration_id = models.ForeignKey(
        StaffAccessConfiguration,
        on_delete=models.CASCADE,
        to_field="unique_id",
        db_column="staff_access_configuration_id",
        related_name="granted_permissions",
    )

    mainscreen_id = models.ForeignKey(
        MainScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="mainscreen_id",
        related_name="staff_access_configuration_permissions",
    )
    userscreen_id = models.ForeignKey(
        UserScreen, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreen_id",
        related_name="staff_access_configuration_permissions",
    )
    userscreenaction_id = models.ForeignKey(
        UserScreenAction, on_delete=models.PROTECT,
        to_field="unique_id", db_column="userscreenaction_id",
        related_name="staff_access_configuration_permissions",
    )

    order_no = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_no"]
        constraints = [
            UniqueConstraint(
                fields=[
                    "staff_access_configuration_id",
                    "userscreen_id",
                    "userscreenaction_id",
                ],
                condition=models.Q(is_deleted=False),
                name="uq_active_staff_access_configuration_permission",
            )
        ]

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
