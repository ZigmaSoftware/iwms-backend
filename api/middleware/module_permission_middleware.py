# api/middleware/module_permission.py

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.customercreation import CustomerCreation


HTTP_ACTION_MAP = {
    "POST": "add",
    "GET": "view",
    "HEAD": "view",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}

PROTECTED_MODULES = [
    "masters",
    "assets",
    "role-assign",
    "user-creation",
    "customers",
    "vehicles",
    "grievance",
]

AUTH_ONLY_PREFIXES = (
    "/api/mobile/main-category/",
    "/api/mobile/sub-category/",
    "/api/desktop/main-category/",
    "/api/desktop/sub-category/",
    "/api/desktop/register/",
    "/api/desktop/recognize/",
    "/api/desktop/employee/",
    "/api/desktop/staff-profile/",
    "/api/desktop/waste/",
    "/api/desktop/attendance-list/",
)

# Platform routes that should bypass all middleware permission checks
PLATFORM_PREFIXES = (
    "/api/platform/",
)

PUBLIC_PREFIXES = (
    "/media/",
)

# Explicitly declare which resources are valid under each protected module.
# This keeps permission checks predictable and lets us whitelist new endpoints centrally.
MODULE_RESOURCE_ALLOWLIST = {
    "masters": {
        "Continent",
        "Country",
        "State",
        "District",
        "City",
        "Zone",
        "Ward",
        "Bin",
    },
    "assets": {
        "Fuel",
        "Property",
        "SubProperty",
        "ZonePropertyLoadTracker",
    },
    "role-assign": {
        "UserType",
        "Staffusertypes",
    },
    "user-creation": {
        "UsersCreation",
        "StaffCreation",
        "StaffTemplateCreation",
        "AlternativeStaffTemplate",
        "RoutePlan",
        "SupervisorZoneMap",
        "SupervisorZoneAccessAudit",
        "StaffTemplateAuditLog",
        "UnassignedStaffPool",
    },
    "customers": {
        "Customercreations",
        "Wastecollections",
        "Feedbacks",
        "Complaints",
    },
    "vehicles": {
        "VehicleTypeCreation",
        "VehicleCreation",
        "TripDefinition",
        "BinLoadLog",
        "TripInstance",
        "TripAttendance",
        "VehicleTripAudit",
        "TripExceptionLog",
    },
    "grievance": {
        "MainCategory",
        "SubCategory",
    },
}


def _split_path(path):
    return [p for p in path.split("?")[0].split("/") if p]


def _module_and_resource_from_path(path):
    parts = _split_path(path)
    for i, part in enumerate(parts):
        if part in PROTECTED_MODULES:
            return part, None
    return None, None


def _extract_token(request):
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    return auth.replace("Bearer ", "").strip()


def _authenticate_request(request):
    auth = request.headers.get("Authorization")

    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"detail": "Authorization token missing"}, status=401)

    token = auth.split(" ", 1)[1].strip()
    # Remove all whitespace characters including newlines from the token
    token = ''.join(token.split())

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return JsonResponse({"detail": "Token expired"}, status=401)
    except jwt.InvalidTokenError:
        return JsonResponse({"detail": "Invalid token"}, status=401)

    unique_id = payload.get("unique_id")
    if not unique_id:
        return JsonResponse({"detail": "Invalid token payload"}, status=401)

    # Try to find user in StaffOfficeDetails first (uses staff_unique_id)
    staff = StaffOfficeDetails.objects.filter(staff_unique_id=unique_id).first()
    if staff:
        request.user = staff
        request.jwt_payload = payload
        if hasattr(request, "_request"):
            request._request.user = staff
        return None
    
    # Try to find user in CustomerCreation (uses unique_id)
    customer = CustomerCreation.objects.filter(unique_id=unique_id).first()
    if customer:
        request.user = customer
        request.jwt_payload = payload
        if hasattr(request, "_request"):
            request._request.user = customer
        return None

    # Fall back to Django User (platform super admins)
    UserModel = get_user_model()
    user = UserModel.objects.filter(unique_id=unique_id).first()
    if not user:
        user_id = payload.get("user_id")
        if user_id:
            user = UserModel.objects.filter(pk=user_id).first()
    if user:
        request.user = user
        request.jwt_payload = payload
        if hasattr(request, "_request"):
            request._request.user = user
        return None

    return JsonResponse({"detail": "User not found"}, status=401)

class ModulePermissionMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):

        if request.method == "OPTIONS":
            return None

        if any(request.path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        # Bypass all middleware checks for platform routes
        if any(request.path.startswith(p) for p in PLATFORM_PREFIXES):
            return None

        if any(request.path.startswith(p) for p in AUTH_ONLY_PREFIXES):
            auth_error = _authenticate_request(request)
            if auth_error:
                return auth_error
            if getattr(request.user, "is_superuser", False):
                return JsonResponse(
                    {"detail": "Platform super admin cannot use business endpoints"},
                    status=403,
                )
            return None

        module, _ = _module_and_resource_from_path(request.path)
        if not module:
            return None

        auth_error = _authenticate_request(request)
        if auth_error:
            return auth_error

        if getattr(request.user, "is_superuser", False):
            return JsonResponse(
                {"detail": "Platform super admin cannot use business endpoints"},
                status=403,
            )

        payload = request.jwt_payload
        role = (payload.get("role") or "").lower()

        if role == "admin":
            return None

        view_class = getattr(view_func, "cls", None)
        if not view_class:
            return None

        permission_resource = getattr(
            view_class,
            "permission_resource",
            view_class.__name__.replace("ViewSet", "")
        )

        allowed_resources = MODULE_RESOURCE_ALLOWLIST.get(module, set())
        if permission_resource not in allowed_resources:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": permission_resource,
                    "reason": "Resource not allowed",
                },
                status=403
            )

        action = HTTP_ACTION_MAP.get(request.method)
        if not action:
            return JsonResponse({"detail": "Invalid method"}, status=405)

        permissions = payload.get("permissions", {})
        allowed_actions = permissions.get(module, {}).get(permission_resource, [])

        if action not in allowed_actions:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": permission_resource,
                    "action": action,
                },
                status=403
            )

        return None
