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

    # ======================================================
    # ALLOW RETRIEVE TO SEE SOFT-DELETED RECORDS
    # ======================================================
    def get_queryset(self):
        # list → only active
        if self.action in ["list"]:
            return UserScreenPermission.objects.filter(is_deleted=False)

        # retrieve/delete → include deleted
        return UserScreenPermission.objects.all()

    # ======================================================
    # GET /desktop/userscreenpermissions/<id>/
    # ======================================================
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()  # now includes deleted
        serializer = UserScreenPermissionSerializer(instance)
        return Response(serializer.data)

    # ======================================================
    # POST (bulk-sync for multi screens)
    # ======================================================
    @action(
        detail=False,
        methods=["post"],
        url_path=r"bulk-sync-multi/(?P<staffusertype_id>[^/.]+)"
    )
    def bulk_sync_multi(self, request, staffusertype_id):
        data = dict(request.data)
        data["staffusertype_id"] = staffusertype_id

        with transaction.atomic():
            serializer = UserScreenPermissionMultiScreenSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()

        return Response({
            "created": UserScreenPermissionSerializer(result["created"], many=True).data,
            "updated": UserScreenPermissionSerializer(result["updated"], many=True).data,
            "deleted": UserScreenPermissionSerializer(result["deleted"], many=True).data,
        }, status=status.HTTP_200_OK)

    # ======================================================
    # GET → By Staff User Type + Mainscreen (formatted)
    # ======================================================
    @action(
        detail=False,
        methods=["get"],
        url_path="by-staff-format"
    )
    def by_staff_format(self, request):
        staffusertype_id = request.query_params.get("staffusertype_id")
        mainscreen_id = request.query_params.get("mainscreen_id")

        if not staffusertype_id:
            return Response({"error": "staffusertype_id is required"}, status=400)
        if not mainscreen_id:
            return Response({"error": "mainscreen_id is required"}, status=400)

        qs = UserScreenPermission.objects.filter(
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id,
            is_deleted=False
        )

        if not qs.exists():
            return Response({"detail": "No permissions found"}, status=404)

        usertype_id = qs.first().usertype_id_id

        screen_map = {}
        for perm in qs:
            scr = perm.userscreen_id_id
            act = perm.userscreenaction_id_id

            if scr not in screen_map:
                screen_map[scr] = {
                    "userscreen_id": scr,
                    "actions": []
                }
            screen_map[scr]["actions"].append(act)

        result = {
            "usertype_id": usertype_id,
            "staffusertype_id": staffusertype_id,
            "mainscreen_id": mainscreen_id,
            "screens": list(screen_map.values()),
            "description": qs.first().description or ""
        }

        return Response(result, status=200)

    # ======================================================
    # DELETE ALL PERMISSIONS BY STAFF USER TYPE
    # ======================================================
    @action(
        detail=False,
        methods=["delete"],
        url_path=r"delete-by-staffusertype/(?P<staffusertype_id>[^/.]+)"
    )
    def delete_by_staffusertype(self, request, staffusertype_id):

        # Include deleted as well → allow re-deleting without errors
        qs = UserScreenPermission.objects.filter(
            staffusertype_id_id=staffusertype_id
        )

        if not qs.exists():
            return Response({"detail": "No permissions found"}, status=404)

        deleted_count = qs.count()

        qs.update(is_deleted=True, is_active=False)

        return Response({
            "message": "Permissions deleted successfully",
            "deleted_count": deleted_count,
            "staffusertype_id": staffusertype_id
        }, status=200)
