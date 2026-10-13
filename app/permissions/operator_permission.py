from rest_framework.permissions import BasePermission

from app.permissions.platform import _role_name


class IsOperatorRole(BasePermission):
    """Allow Staffcreation users whose role is driver, operator, or any other
    field-crew role — the driver app was merged with the operator app so a
    driver can also receive/collect trips, but the operator module/role
    itself was NOT removed and must keep working independently too.

    Substring match (not an exact-name allowlist) so role names like
    "Company Driver", "Company Operator", "Field Operator" all pass without
    needing every exact variant enumerated.
    """

    message = "Driver or operator role required"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        role_names = [(_role_name(user) or "").lower()]
        contractor_role = getattr(user, "contractorusertype", None)
        contractor_role_name = (getattr(contractor_role, "name", "") or "").lower()
        if contractor_role_name:
            role_names.append(contractor_role_name)
        field_role_markers = ("driver", "operator", "field")
        return any(
            marker in role_name
            for role_name in role_names
            for marker in field_role_markers
        )
