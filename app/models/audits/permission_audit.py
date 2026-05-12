from django.db import models

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.user_creations.staffcreation import Staffcreation


class PermissionAuditLog(models.Model):
    """Track permission updates for audit trail."""   

    ACTION_CHOICES = [
        ("create", "Created"),
        ("update", "Updated"),
        ("delete", "Deleted"),
    ]

    permission = models.ForeignKey(
        CompanyUserScreenPermission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    updated_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permission_audit_logs"
        ordering = ["-timestamp"]