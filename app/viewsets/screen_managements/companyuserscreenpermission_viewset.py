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
#     # put → BY STAFF USER TYPE + MAINSCREEN
#     # ---------------------------------------------------------


#     @action(
#     detail=False,
#     methods=["put"],
#     url_path=r"update-by-staffusertype/(?P<staffusertype_id>[^/.]+)"
# )
#     def update_by_staffusertype(self, request, staffusertype_id):

#         company_id = request.data.get("company_id")
#         mainscreen_id = request.data.get("mainscreen_id")

#         if not company_id or not mainscreen_id:
#             return Response(
#                 {"error": "company_id and mainscreen_id are required"},
#                 status=400
#             )

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



from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.superadmin_masters.company import Company
from app.serializers.screen_managements.companyuserscreenpermission_serializer import (
    CompanyUserScreenPermissionMultiScreenSerializer,
    CompanyUserScreenPermissionSerializer,
)

from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class CompanyUserScreenPermissionViewSet(CompanyScopedViewSet):
    serializer_class = CompanyUserScreenPermissionSerializer
    lookup_field = "unique_id"

    # Makes newest records appear first on page 1
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at", "-created_at"]

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _company_from_request(self, request, source="query", required=True):
        """
        Resolves company from middleware scope first, then from request.
        Supports both company_id and company_unique_id.
        Returns: (company_obj_or_none, error_response_or_none)
        """
        scoped_company = self._company()
        if scoped_company:
            return scoped_company, None

        payload = request.query_params if source == "query" else request.data
        company_id = payload.get("company_id") or payload.get("company_unique_id")

        if not company_id:
            if required:
                return None, Response(
                    {"error": "company_id (or company_unique_id) is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return None, None

        company = Company.objects.filter(unique_id=company_id).first()
        if not company:
            return None, Response({"error": "Invalid company"}, status=status.HTTP_400_BAD_REQUEST)

        return company, None

    def _sync_permissions(self, request, staffusertype_id, update_only=False):
        company, error = self._company_from_request(request, source="data", required=True)
        if error:
            return error

        payload = request.data.copy()
        payload["company_id"] = company.unique_id
        payload["staffusertype_id"] = staffusertype_id

        with transaction.atomic():
            serializer = CompanyUserScreenPermissionMultiScreenSerializer(
                data=payload,
                context={"update_only": update_only},
            )
            serializer.is_valid(raise_exception=True)
            result = serializer.save()

        return Response(
            {
                "created": CompanyUserScreenPermissionSerializer(result["created"], many=True).data,
                "updated": CompanyUserScreenPermissionSerializer(result["updated"], many=True).data,
                "deleted": CompanyUserScreenPermissionSerializer(result["deleted"], many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Queryset
    # ---------------------------------------------------------
    def get_queryset(self):
        company, _ = self._company_from_request(self.request, source="query", required=False)

        qs = CompanyUserScreenPermission.objects.filter(is_deleted=False)

        # Safety: avoid returning all companies when no company scope/filter is present
        if not company:
            return qs.none()

        return qs.filter(company_id_id=company.unique_id)

    # ---------------------------------------------------------
    # Retrieve
    # ---------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    # ---------------------------------------------------------
    # Bulk Sync / Update
    # ---------------------------------------------------------
    @action(detail=False, methods=["post"], url_path=r"bulk-sync-multi/(?P<staffusertype_id>[^/.]+)")
    def bulk_sync_multi(self, request, staffusertype_id):
        return self._sync_permissions(request, staffusertype_id, update_only=False)

    @action(detail=False, methods=["post", "put"], url_path=r"update-by-staffusertype/(?P<staffusertype_id>[^/.]+)")
    def update_by_staffusertype(self, request, staffusertype_id):
        return self._sync_permissions(request, staffusertype_id, update_only=True)

    # ---------------------------------------------------------
    # By Staff + Mainscreen
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="by-staff-format")
    def by_staff_format(self, request):
        company, error = self._company_from_request(request, source="query", required=True)
        if error:
            return error

        staffusertype_id = request.query_params.get("staffusertype_id")
        mainscreen_id = request.query_params.get("mainscreen_id")

        if not staffusertype_id or not mainscreen_id:
            return Response(
                {"error": "staffusertype_id and mainscreen_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
        )

        # Return 200 empty payload (frontend-friendly)
        if not qs.exists():
            return Response(
                {
                    "company_id": company.unique_id,
                    "staffusertype_id": staffusertype_id,
                    "mainscreen_id": mainscreen_id,
                    "usertype_id": None,
                    "screens": [],
                    "description": "",
                },
                status=status.HTTP_200_OK,
            )

        screen_map = {}
        for perm in qs:
            scr = perm.userscreen_id_id
            act = perm.userscreenaction_id_id
            screen_map.setdefault(scr, {"userscreen_id": scr, "actions": []})["actions"].append(act)

        first = qs.first()
        return Response(
            {
                "company_id": company.unique_id,
                "usertype_id": first.usertype_id_id if first else None,
                "staffusertype_id": staffusertype_id,
                "mainscreen_id": mainscreen_id,
                "screens": list(screen_map.values()),
                "description": (first.description or "") if first else "",
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Delete By Staff + Mainscreen (safe delete)
    # ---------------------------------------------------------
    @action(detail=False, methods=["delete"], url_path=r"delete-by-staffusertype/(?P<staffusertype_id>[^/.]+)/?")
    def delete_by_staffusertype(self, request, staffusertype_id):
        company, error = self._company_from_request(request, source="query", required=True)
        if error:
            return error

        mainscreen_id = request.query_params.get("mainscreen_id")
        if not mainscreen_id:
            return Response(
                {"error": "mainscreen_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
        )

        deleted_count = qs.count()
        if deleted_count > 0:
            qs.update(is_deleted=True, is_active=False)

        return Response(
            {
                "message": "Permissions deleted successfully",
                "deleted_count": deleted_count,
                "staffusertype_id": staffusertype_id,
                "mainscreen_id": mainscreen_id,
                "company_id": company.unique_id,
            },
            status=status.HTTP_200_OK,
        )
