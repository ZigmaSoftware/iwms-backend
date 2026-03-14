# from rest_framework import status
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from django.db import transaction

# from app.models.superadmin_masters.company import Company
# from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
# from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
# from app.serializers.screen_managements.companyuserscreenpermission_serializer import (
#     CompanyUserScreenPermissionSerializer,
#     CompanyUserScreenPermissionMultiScreenSerializer,
# )


# class CompanyUserScreenPermissionViewSet(CompanyScopedViewSet):
#     serializer_class = CompanyUserScreenPermissionSerializer
#     lookup_field = "unique_id"

#     # ---------------------------------------------------------
#     # QUERYSET (Company Scoped)
#     # ---------------------------------------------------------
#     def get_queryset(self):

#         company = self._company()

#         # If middleware provides company
#         if company:
#             return CompanyUserScreenPermission.objects.filter(
#                 company_id_id=company.unique_id,
#                 is_deleted=False
#             )

#         # fallback → read company_id from query params
#         company_id = self.request.query_params.get("company_id")

#         if not company_id:
#             return CompanyUserScreenPermission.objects.filter(is_deleted=False)

#         return CompanyUserScreenPermission.objects.filter(
#             company_id_id=company_id,
#             is_deleted=False
#         )

#     # ---------------------------------------------------------
#     # RETRIEVE
#     # ---------------------------------------------------------
#     def retrieve(self, request, *args, **kwargs):
#         instance = self.get_object()
#         serializer = self.get_serializer(instance)
#         return Response(serializer.data)

#     # ---------------------------------------------------------
#     # BULK SYNC MULTI SCREEN
#     # ---------------------------------------------------------
#     @action(
#         detail=False,
#         methods=["post"],
#         url_path=r"bulk-sync-multi/(?P<staffusertype_id>[^/.]+)"
#     )
#     def bulk_sync_multi(self, request, staffusertype_id):

#         company_id = request.data.get("company_id")

#         if not company_id:
#             return Response({"error": "company_id is required"}, status=400)

#         company = Company.objects.filter(unique_id=company_id).first()

#         if not company:
#             return Response({"error": "Invalid company"}, status=400)

#         data = dict(request.data)
#         data["staffusertype_id"] = staffusertype_id
#         data["company_id"] = company.unique_id

#         with transaction.atomic():
#             serializer = CompanyUserScreenPermissionMultiScreenSerializer(data=data)
#             serializer.is_valid(raise_exception=True)
#             result = serializer.save()

#         return Response({
#             "created": CompanyUserScreenPermissionSerializer(
#                 result["created"], many=True
#             ).data,
#             "updated": CompanyUserScreenPermissionSerializer(
#                 result["updated"], many=True
#             ).data,
#             "deleted": CompanyUserScreenPermissionSerializer(
#                 result["deleted"], many=True
#             ).data,
#         }, status=status.HTTP_200_OK)

#     # ---------------------------------------------------------
#     # GET → BY STAFF USER TYPE + MAINSCREEN
#     # ---------------------------------------------------------
#     @action(detail=False, methods=["get"], url_path="by-staff-format")
#     def by_staff_format(self, request):

#         company_id = request.query_params.get("company_id")
#         staffusertype_id = request.query_params.get("staffusertype_id")
#         mainscreen_id = request.query_params.get("mainscreen_id")

#         if not company_id or not staffusertype_id or not mainscreen_id:
#             return Response(
#                 {"error": "company_id, staffusertype_id and mainscreen_id are required"},
#                 status=400,
#             )

#         company = Company.objects.filter(unique_id=company_id).first()

#         if not company:
#             return Response({"error": "Invalid company"}, status=400)

#         qs = CompanyUserScreenPermission.objects.filter(
#             company_id_id=company.unique_id,
#             staffusertype_id_id=staffusertype_id,
#             mainscreen_id_id=mainscreen_id,
#             is_deleted=False,
#         )

#         if not qs.exists():
#             return Response({"detail": "No permissions found"}, status=404)

#         screen_map = {}

#         for perm in qs:
#             scr = perm.userscreen_id_id
#             act = perm.userscreenaction_id_id

#             screen_map.setdefault(scr, {
#                 "userscreen_id": scr,
#                 "actions": []
#             })["actions"].append(act)

#         return Response({
#             "company_id": company.unique_id,
#             "usertype_id": qs.first().usertype_id_id,
#             "staffusertype_id": staffusertype_id,
#             "mainscreen_id": mainscreen_id,
#             "screens": list(screen_map.values()),
#             "description": qs.first().description or "",
#         })

#     # ---------------------------------------------------------
#     # DELETE BY STAFF USER TYPE
#     # ---------------------------------------------------------
#     @action(
#         detail=False,
#         methods=["delete"],
#         url_path=r"delete-by-staffusertype/(?P<staffusertype_id>[^/.]+)/?",
#     )
#     def delete_by_staffusertype(self, request, staffusertype_id):

#         company_id = request.query_params.get("company_id")

#         if not company_id:
#             return Response({"error": "company_id is required"}, status=400)
        
#         company = Company.objects.filter(unique_id=company_id).first()

#         if not company:
#             return Response({"error": "Invalid company"}, status=400)

#         qs = CompanyUserScreenPermission.objects.filter(
#             company_id_id=company.unique_id,
#             staffusertype_id_id=staffusertype_id,
#         )

#         if not qs.exists():
#             return Response({"detail": "No permissions found"}, status=404)

#         deleted_count = qs.count()
#         qs.update(is_deleted=True, is_active=False)

#         return Response({
#             "message": "Permissions deleted successfully",
#             "deleted_count": deleted_count,
#             "staffusertype_id": staffusertype_id,
#         })



from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction

from app.models.superadmin_masters.company import Company
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
    # HELPER — clean query param (strips accidental slashes/spaces)
    # ---------------------------------------------------------
    def _get_param(self, key):
        return self.request.query_params.get(key, "").strip().strip("/")

    # ---------------------------------------------------------
    # QUERYSET (Company Scoped)
    # ---------------------------------------------------------
    def get_queryset(self):
        company = self._company()

        if company:
            return CompanyUserScreenPermission.objects.filter(
                company_id_id=company.unique_id,
                is_deleted=False
            )

        company_id = self._get_param("company_id")   # ✅ strips trailing slash

        if not company_id:
            return CompanyUserScreenPermission.objects.filter(is_deleted=False)

        return CompanyUserScreenPermission.objects.filter(
            company_id_id=company_id,
            is_deleted=False
        )

    # ---------------------------------------------------------
    # RETRIEVE
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
        company_id = request.data.get("company_id", "").strip().strip("/")

        if not company_id:
            return Response({"error": "company_id is required"}, status=400)

        company = Company.objects.filter(unique_id=company_id).first()

        if not company:
            return Response({"error": "Invalid company"}, status=400)

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
    # GET → BY STAFF USER TYPE + MAINSCREEN
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="by-staff-format")
    def by_staff_format(self, request):
        company_id       = self._get_param("company_id")       # ✅ strips slash
        staffusertype_id = self._get_param("staffusertype_id")
        mainscreen_id    = self._get_param("mainscreen_id")

        if not company_id or not staffusertype_id or not mainscreen_id:
            return Response(
                {"error": "company_id, staffusertype_id and mainscreen_id are required"},
                status=400,
            )

        company = Company.objects.filter(unique_id=company_id).first()

        if not company:
            return Response({"error": "Invalid company"}, status=400)

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
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
    # DELETE BY STAFF USER TYPE
    # ---------------------------------------------------------
    @action(
        detail=False,
        methods=["delete"],
        url_path=r"delete-by-staffusertype/(?P<staffusertype_id>[^/.]+)/?",
    )
    def delete_by_staffusertype(self, request, staffusertype_id):
        # ✅ strip trailing slash — API helper appends it after query string
        company_id = self._get_param("company_id")
        mainscreen_id = self._get_param("mainscreen_id")
        staffusertype_id = staffusertype_id.strip().strip("/")

        if not company_id:
            return Response({"error": "company_id is required"}, status=400)
        
        if not mainscreen_id:
            return Response({"error": "mainscreen_id is required"}, status=400)

        company = Company.objects.filter(unique_id=company_id).first()

        if not company:
            return Response({"error": "Invalid company"}, status=400)

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,   # ✅ only delete active records
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