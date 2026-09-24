from django.db import models

from app.utils.comfun import generate_unique_id


def generate_staff_template_audit_id():
    return f"STAUDIT-{generate_unique_id()}"


class StaffTemplateAuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        MODIFY = "MODIFY", "Modify"
        DELETE = "DELETE", "Delete"

    class PerformedRole(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        SUPERVISOR = "SUPERVISOR", "Supervisor"

    class EntityType(models.TextChoices):
        STAFF_TEMPLATE = "STAFF_TEMPLATE", "Staff Template"
        ALT_STAFF_TEMPLATE = "ALT_STAFF_TEMPLATE", "Alternative Staff Template"

    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        default=generate_staff_template_audit_id,
        editable=False,
    )
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    entity_id = models.CharField(max_length=60)
    action = models.CharField(max_length=10, choices=Action.choices)
    performed_by = models.CharField(max_length=30, null=True, blank=True)
    performed_role = models.CharField(max_length=15, choices=PerformedRole.choices)
    change_remarks = models.TextField(null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_template_audit_logs"
        ordering = ["-performed_at"]

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
    def performed_by_staff(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        if self.performed_by:
            return Staffcreation.objects.filter(staff_unique_id=self.performed_by).first()
        return None
