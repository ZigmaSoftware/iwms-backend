# api/utils/audit_context_resolver.py

HTTP_ACTION_MAP = {
    "POST": "add",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}


SUPPORTED_MODULES = {
    "masters",
    "assets",
    "role-assign",
    "user-creation",
    "customers",
    "vehicles",
}


def _extract_desktop_segments(path):
    """Return the path parts after /api/desktop/."""

    clean = path.split("?", 1)[0].strip("/")
    if not clean:
        return []

    parts = [segment for segment in clean.split("/") if segment]

    # Remove the leading api/desktop prefix when present
    if len(parts) >= 2 and parts[0] == "api" and parts[1] == "desktop":
        return parts[2:]

    if parts and parts[0] == "api":
        return parts[1:]

    return parts


def resolve_audit_context(request, view_func):
    segments = _extract_desktop_segments(request.path)
    if len(segments) < 2:
        return None

    module_slug, resource_slug = segments[0], segments[1]
    if module_slug not in SUPPORTED_MODULES:
        return None

    view_class = getattr(view_func, "cls", None)
    if not view_class:
        return None

    action = HTTP_ACTION_MAP.get(request.method)
    if not action:
        return None

    resource_name = view_class.__name__.replace("ViewSet", "")

    return {
        "module_slug": module_slug,
        "resource_slug": resource_slug,
        "resource_name": resource_name,
        "action": action,
    }
