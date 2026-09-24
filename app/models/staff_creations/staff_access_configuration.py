from django.db import models
from django.db.models import UniqueConstraint

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


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

    staff_id = models.CharField(max_length=30, null=True, blank=True)

    company_id = models.CharField(max_length=30, null=True, blank=True)

    # Store project/geo IDs as comma-separated strings for API integration
    project_ids = models.TextField(blank=True, default="")
    state_ids = models.TextField(blank=True, default="")
    district_ids = models.TextField(blank=True, default="")
    city_ids = models.TextField(blank=True, default="")
    zone_ids = models.TextField(blank=True, default="")
    panchayat_ids = models.TextField(blank=True, default="")
    ward_ids = models.TextField(blank=True, default="")

    # The ONE mobile app this staff member signs into. Nothing selected means
    # the mobile login is refused outright; what they can do once inside comes
    # from the ordinary screen permissions below, which also govern web.
    #
    # A person belongs to a single app — a Driver does not also open the
    # Supervisor shell — so this is a single FK rather than a set of ticks,
    # and it is the only place the app is stored. `Staffcreation.app_module`
    # is a read-only property that reads back through here, so the "which app
    # opens after sign-in" question and the "may they sign in at all"
    # question can no longer be answered differently.
    app_module_id = models.CharField(max_length=30, null=True, blank=True)

    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("granted_permissions",)
    CACHE_SCOPES = ("staff_access_configuration_list", "staff_access_configuration_detail")

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
        return f"{self.staff_id}"

    def get_project_ids(self):
        return [p for p in self.project_ids.split(",") if p]

    def get_state_ids(self):
        return [s for s in self.state_ids.split(",") if s]

    def get_district_ids(self):
        return [d for d in self.district_ids.split(",") if d]

    def get_city_ids(self):
        return [c for c in self.city_ids.split(",") if c]

    def get_zone_ids(self):
        return [z for z in self.zone_ids.split(",") if z]

    def get_panchayat_ids(self):
        return [p for p in self.panchayat_ids.split(",") if p]

    def get_ward_ids(self):
        return [w for w in self.ward_ids.split(",") if w]

    @property
    def staff(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.staff_id).first()
        return None

    @property
    def company(self):
        from app.models.superadmin_masters.company import Company
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None

    @property
    def app_module(self):
        from app.models.screen_managements.app_module import AppModule
        if self.app_module_id:
            return AppModule.objects.filter(unique_id=self.app_module_id).first()
        return None

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

    staff_access_configuration_id = models.CharField(max_length=60, null=True, blank=True)

    mainscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreenaction_id = models.CharField(max_length=30, null=True, blank=True)

    order_no = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("staff_access_configuration_permission_list", "staff_access_configuration_permission_detail")

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

    @property
    def staff_access_configuration(self):
        if self.staff_access_configuration_id:
            return StaffAccessConfiguration.objects.filter(unique_id=self.staff_access_configuration_id).first()
        return None

    @property
    def mainscreen(self):
        from app.models.screen_managements.mainscreen import MainScreen
        if self.mainscreen_id:
            return MainScreen.objects.filter(unique_id=self.mainscreen_id).first()
        return None

    @property
    def userscreen(self):
        from app.models.screen_managements.userscreen import UserScreen
        if self.userscreen_id:
            return UserScreen.objects.filter(unique_id=self.userscreen_id).first()
        return None

    @property
    def userscreenaction(self):
        from app.models.screen_managements.userscreenaction import UserScreenAction
        if self.userscreenaction_id:
            return UserScreenAction.objects.filter(unique_id=self.userscreenaction_id).first()
        return None