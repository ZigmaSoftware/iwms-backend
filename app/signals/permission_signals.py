# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission


# @receiver(post_save, sender=CompanyUserScreenPermission)
# def log_permission_change(sender, instance, created, **kwargs):
#     """Log when permissions are created or updated."""
#     from app.models.audits.permission_audit import PermissionAuditLog
    
#     action = "create" if created else "update"
#     PermissionAuditLog.objects.create(
#         permission=instance,
#         action=action,
#         updated_by=instance.updated_by if hasattr(instance, "updated_by") else None
#     )


# @receiver(post_delete, sender=CompanyUserScreenPermission)
# def log_permission_delete(sender, instance, **kwargs):
#     """Log when permissions are deleted."""
#     from app.models.audits.permission_audit import PermissionAuditLog
    
#     PermissionAuditLog.objects.create(
#         permission=None,  # instance already deleted
#         action="delete",
#     )

from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.audits.permission_audit import PermissionAuditLog

from app.models.role_assigns.staffUserType import StaffUserType
from app.models.superadmin_masters.company import Company  # adjust import if different


@receiver(post_save, sender=CompanyUserScreenPermission)
def log_permission_change(sender, instance, created, **kwargs):
    """
    Logs permission changes safely.
    Handles both object + string FK cases.
    """

    try:
        company = instance.company_id
        staffusertype = instance.staffusertype_id

        # ✅ Convert string → model instance (IMPORTANT FIX)
        if isinstance(company, str):
            company = Company.objects.filter(unique_id=company).first()

        if isinstance(staffusertype, str):
            staffusertype = StaffUserType.objects.filter(
                unique_id=staffusertype
            ).first()

        PermissionAuditLog.objects.create(
            company_id=company,
            staffusertype_id=staffusertype,
            mainscreen_id=instance.mainscreen_id,
            userscreen_id=instance.userscreen_id,
            userscreenaction_id=instance.userscreenaction_id,
            is_active=instance.is_active,
            is_deleted=instance.is_deleted,
            action_type="CREATED" if created else "UPDATED",
        )

    except Exception as e:
        # ❗ Never break main API because of logging
        print("❌ Permission Audit Log Error:", str(e))