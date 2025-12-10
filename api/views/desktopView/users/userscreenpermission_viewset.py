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
    # GET /desktop/userscreenpermissions/<id>/
    # ======================================================
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = UserScreenPermissionSerializer(instance)
        return Response(serializer.data)

    # ======================================================
    # POST (bulk) /desktop/userscreenpermissions/bulk-sync-multi/<staffusertype_id>/
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
            "deleted": UserScreenPermissionSerializer(result["deleted"], many=True).data
        }, status=status.HTTP_200_OK)
        
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

        # Get unique usertype
        usertype_id = qs.first().usertype_id_id

        # Group screens + actions
        screen_map = {}

        for perm in qs:
            scr_id = perm.userscreen_id_id
            act_id = perm.userscreenaction_id_id

            if scr_id not in screen_map:
                screen_map[scr_id] = {
                    "userscreen_id": scr_id,
                    "actions": []
                }

            screen_map[scr_id]["actions"].append(act_id)

        # Final response format
        result = {
            "usertype_id": usertype_id,
            "staffusertype_id": staffusertype_id,
            "mainscreen_id": mainscreen_id,
            "screens": list(screen_map.values()),
            "description": qs.first().description if qs.first().description else ""
        }

        return Response(result, status=200)



    # ======================================================
    # SOFT DELETE
    # ======================================================
    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.is_active = False
        instance.save()
