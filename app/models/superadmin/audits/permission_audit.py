from django.db import models


class PermissionAuditLog(models.Model):
    """Track permission updates for audit trail."""

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("UPDATED", "Updated"),
        ("DELETED", "Deleted"),
    ]



    # Where the grant was made. Every current source stores one row per save
    # with the access before and after it (app/utils/permission_snapshot.py):
    # per company/project for COMPANY_*, per person for STAFF/CUSTOMER_ACCESS.
    SOURCE_CHOICES = [
        ("COMPANY_SCREEN", "Company Screen Permission"),
        ("COMPANY_COLUMN", "Company Column Permission"),
        ("STAFF_ACCESS", "Staff Access Configuration"),
        ("CUSTOMER_ACCESS", "Customer Access Configuration"),
        # Per-change rows written before saves were snapshotted.
        ("STAFF_SCREEN", "Staff Access Configuration"),
        ("STAFF_APP", "Staff App Access"),
        ("CUSTOMER_APP", "Customer App Access"),
        ("CUSTOMER_SCREEN", "Customer App Screen"),
    ]
    CURRENT_SOURCES = ("COMPANY_SCREEN", "COMPANY_COLUMN", "STAFF_ACCESS", "CUSTOMER_ACCESS")

    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="COMPANY_SCREEN", db_index=True
    )
    # Who received the access: a staff_unique_id for STAFF_* rows, a customer
    # unique_id for CUSTOMER_* rows. Company-level grants have no single
    # recipient and leave it blank.
    target_id = models.CharField(max_length=60, null=True, blank=True, db_index=True)
    app_module_id = models.CharField(max_length=30, null=True, blank=True)
    column_id = models.CharField(max_length=40, null=True, blank=True)
    # HTTP method of the request that made the change (POST/PUT/PATCH/DELETE).
    http_method = models.CharField(max_length=10, null=True, blank=True)
    # The whole access before and after the save (company/project grants, or
    # one person's); see app/utils/permission_snapshot.py for the shape.
    # Per-change rows from before saves were snapshotted leave both blank.
    old_permissions = models.JSONField(null=True, blank=True)
    new_permissions = models.JSONField(null=True, blank=True)

    company_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    project_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    mainscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreen_id = models.CharField(max_length=30, null=True, blank=True)
    userscreenaction_id = models.CharField(max_length=30, null=True, blank=True)
    # Account.account_id of the actor: a staff_unique_id for staff, or the
    # User.unique_id for platform/company users (up to 50 chars).
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(null=True, blank=True)
    is_deleted = models.BooleanField(null=True, blank=True)
    # State as it stood before this save, captured by the pre_save signal, so
    # the trail shows what changed (granted → revoked) and not only the result.
    previous_is_active = models.BooleanField(null=True, blank=True)
    previous_is_deleted = models.BooleanField(null=True, blank=True)
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

    @property
    def updated_by_user(self):
        from app.models.superadmin_masters.auth_user import User
        if self.updated_by:
            return User.objects.filter(unique_id=self.updated_by).first()
        return None
