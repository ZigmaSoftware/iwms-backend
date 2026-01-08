import jwt
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from api.apps.userCreation import User


# --------------------------------------------------
# HTTP METHOD → PERMISSION ACTION
# --------------------------------------------------
HTTP_ACTION_MAP = {
    "POST": "add",
    "GET": "view",
    "HEAD": "view",      # DRF auto HEAD
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}

# --------------------------------------------------
# MODULES TO PROTECT
# --------------------------------------------------
PROTECTED_MODULES = [
    "masters",
    "assets",
    "role-assign",
    "user-creation",
    "customers",
    "vehicles",
]

# --------------------------------------------------
# AUTH-ONLY ENDPOINTS (TOKEN REQUIRED, NO PERMISSIONS)
# --------------------------------------------------
AUTH_ONLY_PREFIXES = (
    "/api/mobile/main-category/",
    "/api/mobile/sub-category/",
)

# --------------------------------------------------
# PUBLIC PATHS (NO AUTHZ/AUTH)
# --------------------------------------------------
PUBLIC_PREFIXES = (
    "/media/",
)

# --------------------------------------------------
# HARD RESOURCE ALLOWLIST (BUSINESS RULE)
# --------------------------------------------------
MODULE_RESOURCE_ALLOWLIST = {
    # Masters
    "masters": {
        "Continent",
        "Countries",
        "States",
        "Districts",
        "Cities",
        "Zones",
        "Wards",
        "Bins"
    },
    
    # Assets
    "assets": {
        "Fuels",
        "Properties",
        "Subproperties",
    },

    # Role Assign
    "role-assign": {
        "UserType",
        "Staffusertypes",
    },
     # Grievance
    "grievance": {
        "MainCategory",
        "SubCategory",
    },
    # User Creation
    "user-creation": {
        "UsersCreation",
        "Staffcreation",
        "StafftemplateCreation",
        "AlternativeStaffTemplate",
        "StafftemplateAuditLog",
        "SupervisorZoneMap",
        "SupervisorZoneAccessAudit",
    },

    # Customers
    "customers": {
        "Customercreations",
        "Wastecollections",
        "Feedbacks",
        "Complaints",
        "CustomerTag",
    },

    # Vehicles
    "vehicles": {
        "VehicleType",
        "VehicleAssigning",
        "VehicleCreation",
    },
}


def _split_path(path):
    clean = path.split("?", 1)[0]
    return [segment for segment in clean.split("/") if segment]


def _is_auth_only_path(path):
    return any(path.startswith(prefix) for prefix in AUTH_ONLY_PREFIXES)


def _is_public_path(path):
    media_prefix = getattr(settings, "MEDIA_URL", "/media/")
    prefixes = set(PUBLIC_PREFIXES)
    if media_prefix:
        prefixes.add(media_prefix)
    return any(path.startswith(prefix) for prefix in prefixes)


def _module_and_resource_from_path(path):
    parts = _split_path(path)

    for index, segment in enumerate(parts):
        if segment in PROTECTED_MODULES:
            resource_slug = parts[index + 1] if index + 1 < len(parts) else None
            return segment, resource_slug

    return None, None


def _slug_to_resource_name(slug):
    if not slug:
        return None

    label = slug.replace("-", " ").title()
    return label.replace(" ", "")


def _extract_token(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    else:
        token = auth_header.strip()

    return token or None


def _resolve_user_from_payload(payload):
    user_unique_id = payload.get("unique_id")
    user_id = payload.get("user_id")

    if user_unique_id:
        return User.objects.only("unique_id", "staffusertype_id_id").get(
            unique_id=user_unique_id
        )

    if user_id is not None:
        return User.objects.only("unique_id", "staffusertype_id_id").get(
            pk=user_id
        )

    return None


def _authenticate_request(request):
    token = _extract_token(request)
    if not token:
        return JsonResponse(
            {"detail": "Authorization token missing"},
            status=401
        )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        return JsonResponse({"detail": "Token expired"}, status=401)
    except jwt.InvalidTokenError:
        return JsonResponse({"detail": "Invalid token"}, status=401)

    try:
        user = _resolve_user_from_payload(payload)
    except User.DoesNotExist:
        return JsonResponse({"detail": "User not found"}, status=401)

    if not user:
        return JsonResponse({"detail": "Invalid token payload"}, status=401)

    request.user = user
    request.jwt_payload = payload
    return None


class ModulePermissionMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):

        # --------------------------------------------------
        # 1. IDENTIFY MODULE FROM URL
        # --------------------------------------------------
        module, resource_slug = _module_and_resource_from_path(request.path)

        # Allow OPTIONS / CORS preflight
        if request.method == "OPTIONS":
            return None

        if _is_public_path(request.path):
            return None

        if _is_auth_only_path(request.path):
            auth_error = _authenticate_request(request)
            if auth_error:
                return auth_error
            return None

        # Not a protected module → allow
        if not module:
            return None

        # --------------------------------------------------
        # 2. READ AUTHORIZATION HEADER (SAFE)
        # --------------------------------------------------
        auth_error = _authenticate_request(request)
        if auth_error:
            return auth_error

        payload = request.jwt_payload

        # --------------------------------------------------
        # 4. FETCH PERMISSIONS FROM TOKEN
        # --------------------------------------------------
        role = str(payload.get("role") or "").lower()
        if role == "admin":
            return None

        permissions = payload.get("permissions", {})
        module_permissions = permissions.get(module, {})

        # --------------------------------------------------
        # 5. RESOLVE RESOURCE (URL SLUG → SCREEN NAME)
        # --------------------------------------------------
        view_class = getattr(view_func, "cls", None)

        # Swagger / schema / non-ViewSet → allow
        if not view_class:
            return None

        slug_resource = _slug_to_resource_name(resource_slug)
        view_resource = view_class.__name__.replace("ViewSet", "")
        permission_resource = getattr(view_class, "permission_resource", None)

        if not permission_resource:
            permission_resource = slug_resource or view_resource

        # --------------------------------------------------
        # 6. MAP HTTP METHOD → ACTION
        # --------------------------------------------------
        action = HTTP_ACTION_MAP.get(request.method)
        if not action:
            return JsonResponse(
                {"detail": "Invalid request method"},
                status=405
            )

        # --------------------------------------------------
        # 7A. HARD RESOURCE GATE (KEY RULE)
        # --------------------------------------------------
        allowed_resources = MODULE_RESOURCE_ALLOWLIST.get(module, set())

        if permission_resource not in allowed_resources:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": permission_resource,
                    "reason": "Resource not allowed in this module",
                },
                status=403
            )

        # --------------------------------------------------
        # 7B. JWT ACTION CHECK
        # --------------------------------------------------
        allowed_actions = module_permissions.get(permission_resource, [])

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

        # --------------------------------------------------
        # 8. PERMISSION OK
        # --------------------------------------------------
        return None
