import jwt
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


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
PROTECTED_MODULES = ["masters", "assets"]

# --------------------------------------------------
# HARD RESOURCE ALLOWLIST (YOUR BUSINESS RULE)
# --------------------------------------------------
# masters → ONLY Continent allowed
# assets  → NONE allowed for now
MODULE_RESOURCE_ALLOWLIST = {
    "masters": {"Continent"},
    "assets": set(),
}


class ModulePermissionMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):

        # --------------------------------------------------
        # 1. IDENTIFY MODULE FROM URL
        # --------------------------------------------------
        module = next(
            (m for m in PROTECTED_MODULES if f"/{m}/" in request.path),
            None
        )

        # Not a protected module → allow
        if not module:
            return None

        # Allow OPTIONS / CORS preflight
        if request.method == "OPTIONS":
            return None

        # --------------------------------------------------
        # 2. READ AUTHORIZATION HEADER (SAFE)
        # --------------------------------------------------
        auth_header = request.headers.get("Authorization")
        token = None

        if not auth_header:
            return JsonResponse(
                {"detail": "Authorization token missing"},
                status=401
            )

        # Accept:
        # Authorization: Bearer <token>
        # Authorization: <token>
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        else:
            token = auth_header.strip()

        if not token:
            return JsonResponse(
                {"detail": "Authorization token missing"},
                status=401
            )

        # --------------------------------------------------
        # 3. DECODE JWT TOKEN
        # --------------------------------------------------
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

        # --------------------------------------------------
        # 4. FETCH PERMISSIONS FROM TOKEN
        # --------------------------------------------------
        permissions = payload.get("permissions", {})
        module_permissions = permissions.get(module, {})

        # --------------------------------------------------
        # 5. RESOLVE RESOURCE (VIEWSET CLASS)
        # --------------------------------------------------
        # DRF sets view_func.cls for ViewSets
        view_class = getattr(view_func, "cls", None)

        # Swagger / schema / non-ViewSet → allow
        if not view_class:
            return None

        resource = view_class.__name__.replace("ViewSet", "")

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

        if resource not in allowed_resources:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": resource,
                    "reason": "Resource not allowed in this module",
                },
                status=403
            )

        # --------------------------------------------------
        # 7B. JWT ACTION CHECK
        # --------------------------------------------------
        allowed_actions = module_permissions.get(resource, [])

        if action not in allowed_actions:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": resource,
                    "action": action,
                },
                status=403
            )

        # --------------------------------------------------
        # 8. PERMISSION OK
        # --------------------------------------------------
        return None
