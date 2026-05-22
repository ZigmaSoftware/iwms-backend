from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.audits.permission_audit import PermissionAuditLog


@receiver(post_save, sender=CompanyUserScreenPermission)
def log_permission_change(sender, instance, created, **kwargs):
    """
    Logs permission changes safely.
    Handles both object + string FK cases.
    """

    try:
        PermissionAuditLog.objects.create(
            permission=instance,
            action="create" if created else "update",
        )

    except Exception as e:
        # ❗ Never break main API because of logging
        print("❌ Permission Audit Log Error:", str(e))
