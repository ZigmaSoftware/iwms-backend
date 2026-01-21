# api/middleware/module_permission.py

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from api.apps.userCreation import User


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
        "CustomerTag",
        "HouseholdPickupEvent",
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
    token = _extract_token(request)
    if not token:
        return JsonResponse({"detail": "Authorization token missing"}, status=401)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return JsonResponse({"detail": "Token expired"}, status=401)
    except jwt.InvalidTokenError:
        return JsonResponse({"detail": "Invalid token"}, status=401)

    try:
        user = User.objects.get(unique_id=payload.get("unique_id"))
    except User.DoesNotExist:
        return JsonResponse({"detail": "User not found"}, status=401)

    request.user = user
    request.jwt_payload = payload
    return None


class ModulePermissionMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):

        if request.method == "OPTIONS":
            return None

        if any(request.path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        if any(request.path.startswith(p) for p in AUTH_ONLY_PREFIXES):
            return _authenticate_request(request)

        module, _ = _module_and_resource_from_path(request.path)
        if not module:
            return None

        auth_error = _authenticate_request(request)
        if auth_error:
            return auth_error

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
