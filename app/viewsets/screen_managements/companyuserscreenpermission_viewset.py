from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction

from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.serializers.screen_managements.companyuserscreenpermission_serializer import (
    CompanyUserScreenPermissionSerializer,
    CompanyUserScreenPermissionMultiScreenSerializer,
)


class CompanyUserScreenPermissionViewSet(CompanyScopedViewSet):
    serializer_class = CompanyUserScreenPermissionSerializer
    lookup_field = "unique_id"

    # ---------------------------------------------------------
    # QUERYSET (Company Scoped)
    # ---------------------------------------------------------
    def get_queryset(self):
        company_id = self._company()

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company_id
        )

        if self.action == "list":
            return qs.filter(is_deleted=False)

        return qs

    # ---------------------------------------------------------
    # RETRIEVE (include soft-deleted)
    # ---------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ---------------------------------------------------------
    # BULK SYNC MULTI SCREEN
    # ---------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path=r"bulk-sync-multi/(?P<staffusertype_id>[^/.]+)"
    )
    def bulk_sync_multi(self, request, staffusertype_id):

        company = self._company()

        data = dict(request.data)
        data["staffusertype_id"] = staffusertype_id
        data["company_id"] = company.unique_id
        with transaction.atomic():
            serializer = CompanyUserScreenPermissionMultiScreenSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()

        return Response({
            "created": CompanyUserScreenPermissionSerializer(
                result["created"], many=True
            ).data,
            "updated": CompanyUserScreenPermissionSerializer(
                result["updated"], many=True
            ).data,
            "deleted": CompanyUserScreenPermissionSerializer(
                result["deleted"], many=True
            ).data,
        }, status=status.HTTP_200_OK)

    # ---------------------------------------------------------
    # GET → BY STAFF USER TYPE + MAINSCREEN (FORMATTED)
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="by-staff-format")
    def by_staff_format(self, request):

        company = self._company()

        staffusertype_id = request.query_params.get("staffusertype_id")
        mainscreen_id = request.query_params.get("mainscreen_id")

        if not staffusertype_id or not mainscreen_id:
            return Response(
                {"error": "staffusertype_id and mainscreen_id are required"},
                status=400,
            )

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company,
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
        )

        if not qs.exists():
            return Response({"detail": "No permissions found"}, status=404)

        screen_map = {}
        for perm in qs:
            scr = perm.userscreen_id_id
            act = perm.userscreenaction_id_id
            screen_map.setdefault(scr, {
                "userscreen_id": scr,
                "actions": []
            })["actions"].append(act)

        return Response({
            "company_id": company.unique_id,
            "usertype_id": qs.first().usertype_id_id,
            "staffusertype_id": staffusertype_id,
            "mainscreen_id": mainscreen_id,
            "screens": list(screen_map.values()),
            "description": qs.first().description or "",
        })

    # ---------------------------------------------------------
    # DELETE BY STAFF USER TYPE (SOFT DELETE)
    # ---------------------------------------------------------
    @action(
        detail=False,
        methods=["delete"],
        url_path=r"delete-by-staffusertype/(?P<staffusertype_id>[^/.]+)",
    )
    def delete_by_staffusertype(self, request, staffusertype_id):

        company = self._company()

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company,
            staffusertype_id_id=staffusertype_id,
        )

        if not qs.exists():
            return Response({"detail": "No permissions found"}, status=404)

        deleted_count = qs.count()
        qs.update(is_deleted=True, is_active=False)

        return Response({
            "message": "Permissions deleted successfully",
            "deleted_count": deleted_count,
            "staffusertype_id": staffusertype_id,
        })
