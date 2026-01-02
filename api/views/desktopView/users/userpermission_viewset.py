from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db import transaction
from api.apps.userpermission import UserPermission
from api.serializers.desktopView.users.userpermission_serializer import UserPermissionSerializer

class UserPermissionViewSet(viewsets.ModelViewSet):
    queryset = UserPermission.objects.filter(is_delete=False)
    serializer_class = UserPermissionSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data
        if isinstance(data, list):
            saved_records = []
            for item in data:
                obj, _ = UserPermission.objects.update_or_create(
                    user_type_id=item.get("user_type"),
                    main_screen_id=item.get("main_screen"),
                    user_screen_id=item.get("user_screen"),
                    defaults={
                        "permissions": item.get("permissions", {}),
                        "is_active": item.get("is_active", True),
                        "is_delete": item.get("is_delete", False),
                    },
                )
                saved_records.append(obj)
            serializer = self.get_serializer(saved_records, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        item = data
        obj, _ = UserPermission.objects.update_or_create(
            user_type_id=item.get("user_type"),
            main_screen_id=item.get("main_screen"),
            user_screen_id=item.get("user_screen"),
            defaults={
                "permissions": item.get("permissions", {}),
                "is_active": item.get("is_active", True),
                "is_delete": item.get("is_delete", False),
            },
        )
        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.is_delete = True
        instance.save(update_fields=["is_active", "is_delete"])
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)
