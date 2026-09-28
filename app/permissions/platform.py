from rest_framework.permissions import BasePermission, SAFE_METHODS


def _role_name(user):
    """Resolve the staff role name regardless of model type.

    `staffusertype_id` on Staffcreation/auth User is a plain CharField
    holding the StaffUserType unique_id string — NOT a relation — so
    `user.staffusertype_id.name` is always "". The actual relation is the
    `staffusertype` property. Prefer it; fall back to a direct lookup when
    only the id string is available.
    """
    role_obj = getattr(user, "staffusertype", None)
    name = getattr(role_obj, "name", None)
    if name:
        return name
    role_id = getattr(user, "staffusertype_id", None)
    if isinstance(role_id, str) and role_id:
        try:
            from app.models.superadmin.role_management.staffUserType import StaffUserType
            obj = StaffUserType.objects.filter(unique_id=role_id).only("name").first()
            if obj:
                return obj.name
        except Exception:
            pass
    elif role_id is not None:
        return getattr(role_id, "name", "") or ""
    return ""


class PlatformSuperAdminOnly(BasePermission):
    """Allow only platform-level super admins (Django is_superuser) with no company."""

    message = "Platform super admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )


class SuperAdminApprovalPermission(PlatformSuperAdminOnly):
    """Allow only platform super admins to change user login approval state."""

    message = "Only Super Admin can change user approval status"


class CompanyAdminOnly(BasePermission):
    """Allow only company staff users with staff_usertype=admin."""

    message = "Company admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = _role_name(user)
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is not None
            and (role or "").lower() in ["admin","company_admin","company admin","company project admin","company_project_admin"]
        )


class PlatformOrCompanyAdminFullAccess(BasePermission):
    """Allow platform super admins or company staff users with admin role."""

    message = "Platform super admin or company admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        is_platform_super_admin = bool(
            getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )

        role = _role_name(user)
        is_company_admin = bool(
            not getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is not None
            and (role or "").lower() in ["admin","company_admin","company admin","company project admin","company_project_admin"]
        )

        return is_platform_super_admin or is_company_admin




class PlatformOrCompanyAdminOnly(BasePermission):
    """
    Allow:
    - Platform super admin → full access
    - Company admin → read-only access
    """

    message = "Platform super admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return False

        # ✅ Platform Super Admin → Full Access
        is_platform_super_admin = bool(
            getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )

        if is_platform_super_admin:
            return True

        # ✅ Company Admin / Company Project Admin
        role = _role_name(user)
        is_company_admin = bool(
            not getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is not None
            and (role or "").lower() in ["admin","company_admin","company admin","company project admin","company_project_admin"]
        )

        if is_company_admin:
            # 🔒 Allow only SAFE methods (GET, HEAD, OPTIONS)
            return request.method in SAFE_METHODS

        return False


class StaffUserOnly(BasePermission):
    """Allow only tenant/business users (staff/customers). Block platform super admins."""

    message = "Staff user only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is not None
        )
