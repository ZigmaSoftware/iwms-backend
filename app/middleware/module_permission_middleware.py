import jwt
import re

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from app.models.user_creations.staffcreation import Staffcreation
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.district_leader_login import DistrictLeaderLogin
from app.utils.permission_response import resolve_permission_payload


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
    "localbody/",        # panchayat leader portal — auth only, no module permission check
    "district/",         # district portal — auth only, no module permission check
    "register-fcm-token/",  # staff + citizen FCM device token self-registration
    "attendance/daily-attendance/",  # driver/operator/supervisor attendance screens
    "attendance/staff-profile/",     # same screens' profile calls
    # Self-service permission refresh — authenticate the caller (so the
    # viewset can resolve *their* bundle) but skip the module-permission
    # check, since asking for your own permissions can't itself require one.
    "login/my-permissions/",
)

# Citizen-scoped grievance API — self-service, no module-permission check;
# every query inside the viewset is hard-scoped to the logged-in citizen.
CITIZEN_PREFIXES = tuple(
    prefix + "citizen/"
    for prefix in API_AUTH_PREFIXES
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
    "/api/v1/publicgrievance/",
)

COMMON_AUDIT_CREATE_PATHS = tuple(
    prefix + "audits/common-audit/"
    for prefix in API_AUTH_PREFIXES
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
        "Panchayat",
        "Department",
        "Designation",
        "PanchayatLeaderLogin",
        "DistrictLeaderLogin",
    },
    "waste-types": {
        "Property",
        "SubProperty",
        # merged in from the legacy "assets" module (assets/waste-types,
        # assets/bins now route as waste-types/wastetypes, waste-types/bins)
        "Bin",
        "CollectionPoint",
        "WasteType",
    },
    "screen-managements": {
        "MainScreenType",
        "MainScreen",
        "UserScreen",
        "UserScreenAction",
        "CompanyUserScreenPermission",
        "companywisescreenpermissions",
        "column-permissions",
    },
    "role-assigns": {
        "UserType",
        "StaffUserType",
        "ContractorUserType",
    },
    "user-creations": {
        "StaffCreation",
        "StaffTemplateCreation",
        "AlternativeStaffTemplate",
        "staffaccessconfiguration",
    },
    "customer-masters": {
        "CustomerCreation",
    },
    "complaint-ticket": {
        # renamed from the legacy "grivences" module
        "Complaint",
        "MainCategory",
        "SubCategory",
        # ticketed complaint workflow (app.models.complaint_management)
        "ComplaintModule",
        "ComplaintPriority",
        "ComplaintStatus",
        "ComplaintSource",
        "ComplaintLanguage",
        "ComplaintTeam",
        "ComplaintCategory",
        "ComplaintSubcategory",
        "ComplaintSlaRule",
        "ComplaintRoutingRule",
        "ComplaintFeedback",
        "ComplaintReopenHistory",
        "ComplaintNotification",
        "ComplaintAddressChange",
        "ComplaintTicket",
    },
    "transport-masters": {
        "VehicleTypeCreation",
        "VehicleCreation",
        "Fuel",
    },
    "schedule-setup": {
        # split from the legacy "schedule-masters" module — setup resources
        "StaffTemplateCreation",
        "AlternativeStaffTemplate",
        "CollectionPoint",
        "TripPlan",
    },
    "schedule-operations": {
        # split from the legacy "schedule-masters" module — operational resources
        "DailyTripAssignment",
        "DailyTripCollectionPoint",
        "DailyTripHouseholdCollection",
        "BinCollectionEvent",
        "DailyTripLog",
        "WasteCollection",
        "VehicleBreakdown",
        "TripDelayReport",
        "TripRetripRequest",
        "StaffNotification",
    },
    "schedule-masters": {
        # Legacy permission bucket retained for grants created before Schedule
        # Setup and Daily Operations became separate sidebar/router groups.
        "StaffTemplateCreation",
        "AlternativeStaffTemplate",
        "CollectionPoint",
        "TripPlan",
        "DailyTripAssignment",
        "DailyTripCollectionPoint",
        "DailyTripHouseholdCollection",
        "BinCollectionEvent",
        "DailyTripLog",
        "WasteCollection",
        "VehicleBreakdown",
        "TripDelayReport",
        "TripRetripRequest",
        "DailyWasteComparison",
        "MonthlyWasteComparisonReport",
    },
    "audits": {
        "StaffTemplateAuditLog",
        "LoginAudit",
        "CommonAudit",
    },
}

# alias safety
MODULE_RESOURCE_ALLOWLIST["grivences"] = MODULE_RESOURCE_ALLOWLIST["complaint-ticket"]
MODULE_RESOURCE_ALLOWLIST["grievance"] = MODULE_RESOURCE_ALLOWLIST["complaint-ticket"]

PROTECTED_MODULES = tuple(MODULE_RESOURCE_ALLOWLIST.keys())

MODULE_PERMISSION_ALIASES = {
    "customer-masters": "customers",
    "process-items": "process",
    "grievance": "grivences",
    # "complaint-ticket" is the live URL module (see base_urls.py); permission
    # rows already seeded/granted under the old "grivences" module name keep
    # authorizing it without needing to be re-granted.
    "complaint-ticket": "grivences",
}

# "schedule-setup"/"schedule-operations" are a pure split of the legacy
# "schedule-masters" module, and Bin/WasteType route under "waste-types" but
# were split out of the legacy "assets" module — in both cases the target
# module also has resources genuinely seeded there natively (e.g. TripPlan
# under schedule-setup, Property under waste-types), so a blanket
# MODULE_PERMISSION_ALIASES entry would shadow those. Instead, each listed
# resource's action lookup additionally falls back to the named legacy
# module only when the primary (current) module has no entry for it — see
# _resolve_allowed_actions below.
RESOURCE_MODULE_FALLBACKS = {
    "Bin": "assets",
    "WasteType": "assets",
    "StaffTemplateCreation": "schedule-masters",
    "AlternativeStaffTemplate": "schedule-masters",
    "CollectionPoint": "schedule-masters",
    "TripPlan": "schedule-masters",
    "DailyTripAssignment": "schedule-masters",
    "DailyTripCollectionPoint": "schedule-masters",
    "DailyTripHouseholdCollection": "schedule-masters",
    "BinCollectionEvent": "schedule-masters",
    "DailyTripLog": "schedule-masters",
    "WasteCollection": "schedule-masters",
    "VehicleBreakdown": "schedule-masters",
    "TripDelayReport": "schedule-masters",
    "TripRetripRequest": "schedule-masters",
}

RESOURCE_PERMISSION_ALIASES = {
    "Bin": ("bins",),
    "Department": ("departments", "department-masters"),
    "Designation": ("designations", "designation-masters"),
    "StaffTemplateCreation": ("StaffTemplate", "staff-templates"),
    "VehicleTypeCreation": ("vehicle-type", "vehicle-types"),
    "companywisescreenpermissions": ("CompanyUserScreenPermission",),
    "column-permissions": ("CompanyUserScreenPermission",),
    "staffaccessconfiguration": ("staff-access-configuration",),
}


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


def _route_resource_from_path(path, module):
    parts = _split_path(path)
    try:
        module_index = parts.index(module)
    except ValueError:
        return None

    if module_index + 1 >= len(parts):
        return None

    resource = parts[module_index + 1]
    if resource and not resource.startswith("v"):
        return resource
    return None


def _resource_allowlist_candidates(permission_resource, route_resource=None):
    return {
        candidate
        for candidate in (
            permission_resource,
            route_resource,
            *RESOURCE_PERMISSION_ALIASES.get(permission_resource, ()),
        )
        if candidate
    }


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

    # Panchayat leader (localbody portal)
    leader = PanchayatLeaderLogin.objects.select_related(
        "panchayat_id", "company_id", "project_id"
    ).filter(unique_id=unique_id).first()
    if leader:
        request.user = leader
        request.jwt_payload = payload
        return None

    # District leader (district portal)
    district_leader = DistrictLeaderLogin.objects.select_related(
        "district_id", "company_id", "project_id"
    ).filter(unique_id=unique_id).first()
    if district_leader:
        request.user = district_leader
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


def _permission_filters_for_user(user):
    company = getattr(user, "company_id", None)
    company_unique_id = getattr(company, "unique_id", None)
    staff_unique_id = getattr(user, "staff_unique_id", None)

    if not company_unique_id or not staff_unique_id:
        return None

    # role_name is required so staff with no explicit StaffAccessConfiguration
    # rows still resolve their role's baseline grants (see
    # ROLE_DEFAULT_PERMISSIONS) — otherwise the login response would hand the
    # app permissions that every subsequent request then 403s against.
    role_obj = (
        getattr(user, "staffusertype_id", None)
        or getattr(user, "contractorusertype_id", None)
    )

    return {
        "company_unique_id": company_unique_id,
        "staff_unique_id": staff_unique_id,
        "role_name": getattr(role_obj, "name", None),
    }


def _resolve_permissions_for_request(request):
    payload_permissions = getattr(request, "jwt_payload", {}).get("permissions")
    if payload_permissions:
        return payload_permissions

    filters = _permission_filters_for_user(request.user)
    if not filters:
        return {}

    cache_key = (
        "module-permissions:"
        f"{filters['staff_unique_id']}:"
        f"{filters['company_unique_id']}:"
        f"{filters.get('role_name') or '-'}"
    )

    permissions = cache.get(cache_key)
    if permissions is None:
        permissions = resolve_permission_payload(**filters)["permissions"]
        cache.set(cache_key, permissions, 60)

    return permissions


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

        if (
            request.method == "POST"
            and f"{request.path.rstrip('/')}/" in COMMON_AUDIT_CREATE_PATHS
        ):
            auth_error = _authenticate_request(request)
            return auth_error

        if any(request.path.startswith(p) for p in AUTH_ONLY_PREFIXES):
            auth_error = _authenticate_request(request)
            return auth_error

        if any(request.path.startswith(p) for p in CITIZEN_PREFIXES):
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

        view_class = getattr(view_func, "cls", None)
        if not view_class:
            return None

        permission_resource = getattr(
            view_class,
            "permission_resource",
            view_class.__name__.replace("ViewSet", "")
        )
        route_resource = _route_resource_from_path(request.path, module)

        allowed_resources = MODULE_RESOURCE_ALLOWLIST.get(module, set())
        allowed_resource_keys = {
            self._normalize_permission_key(resource)
            for resource in allowed_resources
        }
        resource_candidates = _resource_allowlist_candidates(
            permission_resource,
            route_resource,
        )
        resource_allowed = any(
            self._normalize_permission_key(candidate) in allowed_resource_keys
            for candidate in resource_candidates
        )

        if not resource_allowed:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": permission_resource,
                    "route_resource": route_resource,
                    "reason": "Resource not allowed",
                },
                status=403,
            )

        action = HTTP_ACTION_MAP.get(request.method)
        if not action:
            return JsonResponse({"detail": "Invalid HTTP method"}, status=405)

        permissions = _resolve_permissions_for_request(request)
        allowed_actions = self._resolve_allowed_actions(
            permissions.get(module, {}),
            permission_resource,
            route_resource,
        )

        if not allowed_actions:
            alias_module = MODULE_PERMISSION_ALIASES.get(module)
            if alias_module:
                allowed_actions = self._resolve_allowed_actions(
                    permissions.get(alias_module, {}),
                    permission_resource,
                    route_resource,
                )

        if not allowed_actions:
            fallback_module = RESOURCE_MODULE_FALLBACKS.get(permission_resource)
            if fallback_module:
                allowed_actions = self._resolve_allowed_actions(
                    permissions.get(fallback_module, {}),
                    permission_resource,
                    route_resource,
                )

        if action not in allowed_actions:
            # A GET is also satisfied by "use" — a lighter-weight grant meant
            # for consuming a screen's records as reference data (e.g. a
            # dropdown option source) without exposing the full list screen.
            if action == "view" and "use" in allowed_actions:
                request.permission_use_only = True
                return None

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

    def _resolve_allowed_actions(self, permissions_map, resource_name, route_resource=None):
        if not permissions_map:
            return []

        resource_candidates = [
            candidate
            for candidate in (
                route_resource,
                resource_name,
                *RESOURCE_PERMISSION_ALIASES.get(resource_name, ()),
            )
            if candidate
        ]

        for candidate in resource_candidates:
            if candidate in permissions_map:
                return permissions_map[candidate]

        for candidate in resource_candidates:
            target = self._normalize_permission_key(candidate)
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
