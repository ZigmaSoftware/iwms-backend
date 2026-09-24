from django.db import models


class PermissionAuditLog(models.Model):
    """Track permission updates for audit trail."""

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("DELETED", "Deleted"),
    ]

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    mainscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreenaction_id = models.CharField(max_length=30, null=True, blank=True)
    updated_by = models.CharField(max_length=30, null=True, blank=True)
    is_active = models.BooleanField(null=True, blank=True)
    is_deleted = models.BooleanField(null=True, blank=True)
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES, default="UPDATED")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permission_audit_logs"
        ordering = ["-timestamp"]

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

    @property
    def updated_by_staff(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        if self.updated_by:
            return Staffcreation.objects.filter(staff_unique_id=self.updated_by).first()
        return None