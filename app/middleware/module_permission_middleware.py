import jwt
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from app.models.user_creations.staffcreation import Staffcreation
from app.models.customers.customercreation import CustomerCreation


# ============================================================
# HTTP → ACTION MAP
# ============================================================

HTTP_ACTION_MAP = {
    "POST": "add",
    "GET": "view",
    "HEAD": "view",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}


# ============================================================
# API PATH CONFIG
# ============================================================

API_AUTH_PREFIXES = (
    "/api/mobile/",
    "/api/desktop/",
    "/api/v1/",
)

AUTH_ONLY_SUFFIXES = (
    "main-category/",
    "sub-category/",
    "register/",
    "recognize/",
    "employee/",
    "staff-profile/",
    "waste/",
    "attendance-list/",
)

AUTH_ONLY_PREFIXES = tuple(
    prefix + suffix
    for prefix in API_AUTH_PREFIXES
    for suffix in AUTH_ONLY_SUFFIXES
)

PLATFORM_PREFIXES = (
    "/api/platform/",
)

PUBLIC_PREFIXES = (
    "/media/",
)


# ============================================================
# MODULE → RESOURCE ALLOWLIST
# (THIS MUST MATCH ViewSet.permission_resource)
# ============================================================

MODULE_RESOURCE_ALLOWLIST = {
    "common-masters": {
        "Continent",
        "Country",
        "State",
    },
    "masters": {
        "District",
        "City",
        "Zone",
        "Ward",
    },
    "waste-types": {
        "Property",
        "SubProperty",
    },
    "assets": {
        "Bin",
    },
    "screen-managements": {
        "MainScreenType",
        "MainScreen",
        "UserScreen",
        "UserScreenAction",
        "CompanyUserScreenPermission",
    },
    "role-assigns": {
        "UserType",
        "StaffUserType",
    },
    "user-creations": {
        "UsersCreation",
        "StaffCreation",
        "StaffTemplateCreation",
        "AlternativeStaffTemplate",
        "SupervisorZoneMap",
        "UnassignedStaffPool",
    },
    "process": {
        "RoutePlan",
        "ZonePropertyLoadTracker",
    },
    "customers": {
        "CustomerCreation",
        "WasteCollection",
        "FeedBack",
        "UserChargeRule",
    },
    "grivences": {
        "Complaint",
        "MainCategory",
        "SubCategory",
    },
    "transport-masters": {
        "VehicleTypeCreation",
        "VehicleCreation",
        "TripDefinition",
        "TripInstance",
        "TripAttendance",
        "Fuel",
    },
    "audits": {
        "VehicleTripAudit",
        "TripExceptionLog",
        "BinLoadLog",
        "SupervisorZoneAccessAudit",
        "StaffTemplateAuditLog",
    },
}

# alias safety
MODULE_RESOURCE_ALLOWLIST["grievance"] = MODULE_RESOURCE_ALLOWLIST["grivences"]

PROTECTED_MODULES = tuple(MODULE_RESOURCE_ALLOWLIST.keys())


# ============================================================
# HELPERS
# ============================================================

def _split_path(path):
    return [p for p in path.split("?")[0].split("/") if p]


def _module_from_path(path):
    parts = _split_path(path)
    for part in parts:
        if part == "api":
            continue
        if part.startswith("v") and part[1:].isdigit():
            continue
        if part in PROTECTED_MODULES:
            return part
    return None


def _authenticate_request(request):
    auth = request.headers.get("Authorization")

    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"detail": "Authorization token missing"}, status=401)

    token = auth.split(" ", 1)[1]
    token = "".join(token.split())

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return JsonResponse({"detail": "Token expired"}, status=401)
    except jwt.InvalidTokenError:
        return JsonResponse({"detail": "Invalid token"}, status=401)

    unique_id = payload.get("unique_id")
    if not unique_id:
        return JsonResponse({"detail": "Invalid token payload"}, status=401)

    # Staff
    staff = Staffcreation.objects.filter(staff_unique_id=unique_id).first()
    if staff:
        request.user = staff
        request.jwt_payload = payload
        return None

    # Customer
    customer = CustomerCreation.objects.filter(unique_id=unique_id).first()
    if customer:
        request.user = customer
        request.jwt_payload = payload
        return None

    # Platform user
    UserModel = get_user_model()
    user = UserModel.objects.filter(unique_id=unique_id).first()
    if not user:
        user_id = payload.get("user_id")
        if user_id:
            user = UserModel.objects.filter(pk=user_id).first()

    if user:
        request.user = user
        request.jwt_payload = payload
        return None

    return JsonResponse({"detail": "User not found"}, status=401)


# ============================================================
# MIDDLEWARE
# ============================================================

class ModulePermissionMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):

        if request.method == "OPTIONS":
            return None

        if any(request.path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        if any(request.path.startswith(p) for p in PLATFORM_PREFIXES):
            return None

        if any(request.path.startswith(p) for p in AUTH_ONLY_PREFIXES):
            auth_error = _authenticate_request(request)
            return auth_error

        module = _module_from_path(request.path)
        if not module:
            return None

        auth_error = _authenticate_request(request)
        if auth_error:
            return auth_error

        if getattr(request.user, "is_superuser", False):
            return None

        payload = request.jwt_payload
        role = (payload.get("role") or "").lower()

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
                status=403,
            )

        action = HTTP_ACTION_MAP.get(request.method)
        if not action:
            return JsonResponse({"detail": "Invalid HTTP method"}, status=405)

        permissions = payload.get("permissions", {})
        allowed_actions = self._resolve_allowed_actions(
            permissions.get(module, {}),
            permission_resource,
        )

        if action not in allowed_actions:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": permission_resource,
                    "action": action,
                },
                status=403,
            )

        return None

    @staticmethod
    def _normalize_permission_key(name):
        if not name:
            return ""
        return re.sub(r"[\W_]+", "", name).lower()

    def _resolve_allowed_actions(self, permissions_map, resource_name):
        if not permissions_map:
            return []

        if resource_name in permissions_map:
            return permissions_map[resource_name]

        target = self._normalize_permission_key(resource_name)
        for key, actions in permissions_map.items():
            normalized = self._normalize_permission_key(key)
            if normalized == target:
                return actions
            if normalized.endswith("s") and normalized[:-1] == target:
                return actions
            if target.endswith("s") and normalized == target[:-1]:
                return actions
            if target.endswith("y") and normalized == target[:-1] + "ies":
                return actions
            if normalized.endswith("y") and normalized[:-1] + "ies" == target:
                return actions

        return []
