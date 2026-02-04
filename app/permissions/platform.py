from rest_framework.permissions import BasePermission


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


class CompanyAdminOnly(BasePermission):
    """Allow only company staff users with staff_usertype=admin."""

    message = "Company admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(getattr(user, "staffusertype_id", None), "name", "")
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is not None
            and (role or "").lower() == "admin"
        )


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
