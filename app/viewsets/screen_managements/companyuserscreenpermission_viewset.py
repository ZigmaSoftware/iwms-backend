from django.core.cache import cache
from rest_framework import status, viewsets
from collections import defaultdict
from app.models.screen_managements.userscreen import UserScreen
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

    permission_resource = "companywisescreenpermissions"

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
    # By Staff + Mainscreen (Shows ALL screens with their actions)
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="by-staff-format")
    def by_staff_format(self, request):
        company = self._company()
        if not company:
            return Response({"error": "company required"}, status=400)

        staffusertype_id = request.query_params.get("staffusertype_id")
        mainscreen_id = request.query_params.get("mainscreen_id")

        if not staffusertype_id or not mainscreen_id:
            return Response(
                {"error": "staffusertype_id and mainscreen_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔥 CACHE KEY
        cache_key = f"perm_{company.unique_id}_{staffusertype_id}_{mainscreen_id}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # 🔥 OPTIMIZED QUERY (NO MODEL LOAD)
        perms = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
        ).values(
            "userscreen_id_id",
            "userscreenaction_id_id",
            "usertype_id_id",
            "description",
        )

        # 🔥 FAST MAP BUILD
        screen_map = defaultdict(list)
        usertype_id = None
        description = ""

        for p in perms:
            screen_map[p["userscreen_id_id"]].append(p["userscreenaction_id_id"])

            if not usertype_id:
                usertype_id = p["usertype_id_id"]

            if not description:
                description = p["description"]

        # 🔥 LIGHTWEIGHT QUERY
        screens_qs = UserScreen.objects.filter(
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
        ).values(
            "unique_id",
            "userscreen_name",
            "folder_name",
            "icon_name",
        )

        # 🔥 FAST RESPONSE BUILD
        screens = [
            {
                "userscreen_id": s["unique_id"],
                "userscreen_name": s["userscreen_name"],
                "folder_name": s["folder_name"],
                "icon_name": s["icon_name"],
                "actions": screen_map.get(s["unique_id"], []),
                "has_permissions": s["unique_id"] in screen_map,
            }
            for s in screens_qs
        ]

        response_data = {
            "company_id": company.unique_id,
            "staffusertype_id": staffusertype_id,
            "usertype_id": usertype_id,
            "mainscreen_id": mainscreen_id,
            "screens": screens,
            "description": description,
        }

        # 🔥 CACHE SAVE (5 min)
        cache.set(cache_key, response_data, timeout=300)

        return Response(response_data)

    # ---------------------------------------------------------
    # All Screens By Staff (across all mainscreens)
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="all-screens-by-staff")
    def all_screens_by_staff(self, request):
        """
        Get ALL screens assigned to a staff user type across all mainscreens.
        Grouped by mainscreen for better visibility.
        
        Query params:
        - staffusertype_id: required
        - company_id: optional (uses middleware scope if available)
        """
        company, error = self._company_from_request(request, source="query", required=True)
        if error:
            return error

        staffusertype_id = request.query_params.get("staffusertype_id")
        if not staffusertype_id:
            return Response(
                {"error": "staffusertype_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get ALL permissions for this company + staff user type (no mainscreen filter)
        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            staffusertype_id_id=staffusertype_id,
            is_deleted=False,
        ).select_related("mainscreen_id", "usertype_id")

        if not qs.exists():
            return Response(
                {
                    "company_id": company.unique_id,
                    "staffusertype_id": staffusertype_id,
                    "mainscreens": [],
                    "total_screens": 0,
                    "usertype_id": None,
                },
                status=status.HTTP_200_OK,
            )

        # Group by mainscreen
        mainscreen_map = {}
        usertype_id = None

        for perm in qs:
            if not usertype_id and perm.usertype_id_id:
                usertype_id = perm.usertype_id_id

            mainscreen_id = perm.mainscreen_id_id
            mainscreen_name = perm.mainscreen_id.mainscreen_name if perm.mainscreen_id else "Unknown"

            if mainscreen_id not in mainscreen_map:
                mainscreen_map[mainscreen_id] = {
                    "mainscreen_id": mainscreen_id,
                    "mainscreen_name": mainscreen_name,
                    "screens": {},
                }

            scr_id = perm.userscreen_id_id
            act_id = perm.userscreenaction_id_id

            if scr_id not in mainscreen_map[mainscreen_id]["screens"]:
                mainscreen_map[mainscreen_id]["screens"][scr_id] = {
                    "userscreen_id": scr_id,
                    "actions": [],
                }

            mainscreen_map[mainscreen_id]["screens"][scr_id]["actions"].append(act_id)

        # Convert to final format
        mainscreens = []
        total_screens = 0
        for mainscreen_data in mainscreen_map.values():
            screens_list = list(mainscreen_data["screens"].values())
            mainscreen_data["screens"] = screens_list
            total_screens += len(screens_list)
            mainscreens.append(mainscreen_data)

        return Response(
            {
                "company_id": company.unique_id,
                "staffusertype_id": staffusertype_id,
                "usertype_id": usertype_id,
                "mainscreens": mainscreens,
                "total_screens": total_screens,
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
