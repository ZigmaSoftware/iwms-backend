from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction

from api.apps.userscreenpermission import UserScreenPermission
from api.serializers.desktopView.users.userscreenpermission_serializer import (
    UserScreenPermissionSerializer,
    UserScreenPermissionMultiScreenSerializer
)


class UserScreenPermissionViewSet(viewsets.ModelViewSet):
    queryset = UserScreenPermission.objects.filter(is_deleted=False)
    serializer_class = UserScreenPermissionSerializer
    lookup_field = "unique_id"

    @action(
        detail=False,
        methods=["post"],
        url_path=r"bulk-sync-multi/(?P<staffusertype_id>[^/.]+)"
    )
    def bulk_sync_multi(self, request, staffusertype_id):
        # FIX: QueryDict mutation → convert to dict
        data = dict(request.data)
        data["staffusertype_id"] = staffusertype_id

        with transaction.atomic():
            serializer = UserScreenPermissionMultiScreenSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()

        return Response({
            "created": UserScreenPermissionSerializer(result["created"], many=True).data,
            "updated": UserScreenPermissionSerializer(result["updated"], many=True).data,
            "deleted": UserScreenPermissionSerializer(result["deleted"], many=True).data
        }, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.is_active = False
        instance.save()
