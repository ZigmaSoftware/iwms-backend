from django.db import models
from app.utils.comfun import generate_unique_id



def generate_login_id():
    return f"AUDITLOG-{generate_unique_id()}"


class AuditLog(models.Model):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    # -------------------------------------------------
    # PRIMARY IDENTIFIER
    # -------------------------------------------------
    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_login_id,
        editable=False
    )

    # -------------------------------------------------
    # WHO performed the action
    # -------------------------------------------------
    user_id = models.CharField(max_length=30)

    # -------------------------------------------------
    # AS WHICH ROLE (snapshot at action time)
    # -------------------------------------------------
    staffusertype_id = models.CharField(max_length=30, null=True, blank=True)

    # -------------------------------------------------
    # WHERE the action occurred
    # -------------------------------------------------
    mainscreen_id = models.CharField(max_length=30)

    userscreen_id = models.CharField(max_length=30)

    # -------------------------------------------------
    # WHAT action was performed
    # -------------------------------------------------
    userscreenaction_id = models.CharField(max_length=30)

    # -------------------------------------------------
    # OUTCOME (MANDATORY)
    # -------------------------------------------------
    success = models.BooleanField()

    reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # -------------------------------------------------
    # FORENSICS / SECURITY
    # -------------------------------------------------
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    user_agent = models.TextField(
        null=True,
        blank=True
    )

    # -------------------------------------------------
    # TIMESTAMP
    # -------------------------------------------------
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    # -------------------------------------------------
    # META CONFIGURATION
    # -------------------------------------------------
    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["staffusertype_id"]),
            models.Index(fields=["mainscreen_id"]),
            models.Index(fields=["userscreen_id"]),
            models.Index(fields=["userscreenaction_id"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.unique_id} | {self.user_id} | {self.userscreenaction_id}"

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
    def user(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        if self.user_id:
            return Staffcreation.objects.filter(staff_unique_id=self.user_id).first()
        return None

    @property
    def staffusertype(self):
        from app.models.superadmin.role_management.staffUserType import StaffUserType
        if self.staffusertype_id:
            return StaffUserType.objects.filter(unique_id=self.staffusertype_id).first()
        return None

    @property
    def mainscreen(self):
        from app.models.superadmin.screen_management.mainscreen import MainScreen
        if self.mainscreen_id:
            return MainScreen.objects.filter(unique_id=self.mainscreen_id).first()
        return None

    @property
    def userscreen(self):
        from app.models.superadmin.screen_management.userscreen import UserScreen
        if self.userscreen_id:
            return UserScreen.objects.filter(unique_id=self.userscreen_id).first()
        return None

    @property
    def userscreenaction(self):
        from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
        if self.userscreenaction_id:
            return UserScreenAction.objects.filter(unique_id=self.userscreenaction_id).first()
        return None
