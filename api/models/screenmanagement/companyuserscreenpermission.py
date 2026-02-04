from django.db import models
from api.utils.tenancy import CompanyProjectMixin
from api.utils.comfun import generate_unique_id
from api.models.screenmanagement.mainscreen import MainScreen
from api.models.screenmanagement.userscreen import UserScreen
from api.models.users.userType import UserType
from api.models.users.staffUserType import StaffUserType
from api.models.screenmanagement.userscreenaction import UserScreenAction
from api.models.superadminmasters.company import Company


def generate_companyuserscreenpermission_id():
    return f"CMPUSERSCRNPERM-{generate_unique_id()}"


class CompanyUserScreenPermission(CompanyProjectMixin, models.Model):
    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_companyuserscreenpermission_id,
        editable=False
    )

    usertype_id = models.ForeignKey(
        UserType, on_delete=models.PROTECT,
        to_field="unique_id", db_column="usertype_id",
        related_name="userscreenpermissions"
    )

    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="staffusertype_id",
        related_name="userscreenpermissions",
        null=True,
        blank=True
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

    order_no = models.IntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_companywiseuserscreenpermission"
        ordering = ["order_no"]
        constraints = [
        models.UniqueConstraint(
            fields=[
                "company_id",
                "usertype_id",
                "staffusertype_id",
                "userscreen_id",
                "userscreenaction_id",
            ],
            name="unique_company_role_screen_action"
        )
        ]


    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
