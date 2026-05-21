from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.audits.permission_audit import PermissionAuditLog

from app.models.role_assigns.staffUserType import StaffUserType
from app.models.superadmin_masters.company import Company


@receiver(post_save, sender=CompanyUserScreenPermission)
def log_permission_change(sender, instance, created, **kwargs):
    try:
        company = instance.company_id
        staffusertype = instance.staffusertype_id

        if isinstance(company, str):
            company = Company.objects.filter(unique_id=company).first()

        if isinstance(staffusertype, str):
            staffusertype = StaffUserType.objects.filter(
                unique_id=staffusertype
            ).first()

        with transaction.atomic():
            PermissionAuditLog.objects.create(
                company=company,
                staffusertype=staffusertype,
                mainscreen=instance.mainscreen_id,
                userscreen=instance.userscreen_id,
                userscreenaction=instance.userscreenaction_id,
                is_active=instance.is_active,
                is_deleted=instance.is_deleted,
                action_type="CREATED" if created else "UPDATED",
            )

    except Exception as e:
        print("❌ Permission Audit Log Error:", str(e))