from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.audits.permission_audit import PermissionAuditLog


@receiver(post_save, sender=CompanyUserScreenPermission)
def log_permission_change(sender, instance, created, **kwargs):
    try:
        PermissionAuditLog.objects.create(
            permission=instance,
            action="create" if created else "update",
        )

    except Exception as e:
        print("❌ Permission Audit Log Error:", str(e))
