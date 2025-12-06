from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from api.apps.userscreenpermission import UserScreenPermission
from api.serializers.desktopView.users.userscreenpermission_serializer import (
    UserScreenPermissionSerializer,
    UserScreenPermissionBulkSerializer
)


class UserScreenPermissionViewSet(viewsets.ModelViewSet):
    queryset = UserScreenPermission.objects.filter(is_deleted=False)
    serializer_class = UserScreenPermissionSerializer
    lookup_field = "unique_id"

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create_permissions(self, request):
        serializer = UserScreenPermissionBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()   # returns dict(created=[], skipped=[])

        return Response({
            "created": UserScreenPermissionSerializer(result["created"], many=True).data,
            "skipped": result["skipped"]
        }, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.is_active = False
        instance.save()
