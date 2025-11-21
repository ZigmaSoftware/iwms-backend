from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import transaction
import json

from api.apps.userpermission import UserPermission
from api.serializers.desktopView.users.userpermission_serializer import (
    UserPermissionSerializer,
)


# Normalizes booleans from strings or null values
def _coerce_bool(value, default):
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        return default

    if value is None:
        return default

    return bool(value)


# Ensures "permissions" is always a dict, not a string
def _ensure_dict(value):
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    return {}


class UserPermissionViewSet(viewsets.ModelViewSet):
    queryset = UserPermission.objects.filter(is_delete=False)
    serializer_class = UserPermissionSerializer

    # Consolidates permission/default logic
    def _build_defaults(self, item):
        return {
            "permissions": _ensure_dict(item.get("permissions")),
            "is_active": _coerce_bool(item.get("is_active"), True),
            "is_delete": _coerce_bool(item.get("is_delete"), False),
        }

    # Insert/Update workflow with atomic transaction
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data

        # ---- Bulk payload support ----
        if isinstance(data, list):
            saved_records = []
            for item in data:
                obj, _ = UserPermission.objects.update_or_create(
                    user_type_id=item.get("user_type"),
                    main_screen_id=item.get("main_screen"),
                    user_screen_id=item.get("user_screen"),
                    defaults=self._build_defaults(item),
                )
                saved_records.append(obj)

            serializer = self.get_serializer(saved_records, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # ---- Single payload ----
        item = data
        obj, _ = UserPermission.objects.update_or_create(
            user_type_id=item.get("user_type"),
            main_screen_id=item.get("main_screen"),
            user_screen_id=item.get("user_screen"),
            defaults=self._build_defaults(item),
        )

        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Soft delete workflow
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.is_delete = True
        instance.save(update_fields=["is_active", "is_delete"])

        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)
