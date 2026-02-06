from typing import Optional

from drf_yasg.inspectors import SwaggerAutoSchema


GROUP_DISPLAY_NAMES = {
    "common-masters": "Common Masters",
    "masters": "Masters",
    "waste-types": "Waste Types",
    "assets": "Assets",
    "screen-managements": "Screen Management",
    "role-assigns": "Role Assign",
    "user-creations": "User Creation",
    "process": "Process",
    "login": "Login",
    "customers": "Customers",
    "grivences": "Grievances",
    "transport-masters": "Transport Masters",
    "audits": "Audits",
    "mobile": "Mobile",
}


def _normalize_segment(segment: str) -> str:
    return segment.strip("/").lower()


def _extract_group_from_path(path: str) -> Optional[str]:
    parts = [p for p in path.split("?")[0].split("/") if p]
    for part in parts:
        normalized = _normalize_segment(part)
        if normalized == "api":
            continue
        if normalized.startswith("v") and normalized[1:].isdigit():
            continue
        if normalized in GROUP_DISPLAY_NAMES:
            return normalized
    return None


class GroupedSwaggerAutoSchema(SwaggerAutoSchema):
    """Base swagger auto schema that tags endpoints by the router group."""

    def get_tags(self, operation_keys=None):
        tags = super().get_tags(operation_keys)
        if tags:
            return tags
        group = _extract_group_from_path(self.path)
        if not group:
            return ["IWMS API"]
        return [GROUP_DISPLAY_NAMES.get(group, group.replace("-", " ").title())]
