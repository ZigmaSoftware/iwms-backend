import csv
import io

from django.core.cache import cache
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from collections import defaultdict
from app.models.screen_managements.userscreen import UserScreen
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.screen_managements.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.serializers.superadmin.screen_management.companyuserscreenpermission_serializer import (
    CompanyUserScreenPermissionMultiScreenSerializer,
    CompanyUserScreenPermissionSerializer,
)
from app.serializers.superadmin.screen_management.companyuserscreencolumnpermission_serializer import (
    CompanyUserScreenColumnPermissionSerializer,
)

from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class CompanyUserScreenPermissionViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    serializer_class = CompanyUserScreenPermissionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "screen-managements"
    AUDIT_ENDPOINT = "company-user-screen-permissions"

    permission_resource = "companywisescreenpermissions"

    # Makes newest records appear first on page 1
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at", "-created_at"]

    def get_serializer_class(self):
        if getattr(self, "action", None) == "create":
            return CompanyUserScreenPermissionMultiScreenSerializer
        return super().get_serializer_class()

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
        company_id = (
            payload.get("company_id")
            or payload.get("companyId")
            or payload.get("company_unique_id")
        )

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

    def _find_project_by_value(self, company, raw_value):
        if not raw_value:
            return None
        value = str(raw_value).strip()
        qs = Project.objects.filter(is_deleted=False)
        if company:
            qs = qs.filter(company_id_id=company.unique_id)
        return qs.filter(Q(unique_id__iexact=value) | Q(name__iexact=value)).first()

    def _normalize_permission_payloads(self, payload):
        if "permissions" not in payload:
            return [payload]

        normalized = []
        for permission in payload.get("permissions", []):
            normalized.append({
                "companyId": payload.get("companyId") or payload.get("company_id"),
                "projectId": payload.get("projectId") or payload.get("project_id"),
                "stateId": payload.get("stateId") or payload.get("state_id"),
                "districtId": payload.get("districtId") or payload.get("district_id"),
                "cityId": payload.get("cityId") or payload.get("city_id"),
                "zoneId": payload.get("zoneId") or payload.get("zone_id"),
                "panchayatId": payload.get("panchayatId") or payload.get("panchayat_id"),
                "wardId": payload.get("wardId") or payload.get("ward_id"),
                "permissionType": payload.get("permissionType") or payload.get("permission_type"),
                "mainScreenId": permission.get("mainScreenId") or permission.get("mainscreen_id"),
                "userScreens": permission.get("userScreens") or permission.get("screens") or [],
                "description": payload.get("description", ""),
            })
        return normalized

    def _sync_nested_permissions(self, request, update_only=False):
        payloads = self._normalize_permission_payloads(request.data)
        results = []

        with transaction.atomic():
            for payload in payloads:
                serializer = CompanyUserScreenPermissionMultiScreenSerializer(
                    data=payload,
                    context={"update_only": update_only},
                )
                serializer.is_valid(raise_exception=True)
                results.append(serializer.save())

        cache.clear()

        return Response(
            {
                "message": "Permissions saved successfully",
                "results": [
                    {
                        "created": len(result["created"]),
                        "updated": len(result["updated"]),
                        "deleted": len(result["deleted"]),
                        "created_columns": len(result["created_columns"]),
                        "updated_columns": len(result["updated_columns"]),
                        "deleted_columns": len(result["deleted_columns"]),
                    }
                    for result in results
                ],
            },
            status=status.HTTP_200_OK,
        )

    def _sync_permissions(
        self,
        request,
        project_id=None,
        update_only=False,
    ):
        company, error = self._company_from_request(request, source="data", required=True)
        if error:
            return error

        # "none" is the sentinel used by the frontend for company-wide
        # (no-project) permissions, since a URL path segment can't be empty.
        if project_id == "none":
            project_id = None
        else:
            project_id = (
                project_id
                or request.data.get("project_id")
                or request.data.get("projectId")
            )

        payload = request.data.copy()
        payload["company_id"] = company.unique_id
        payload["project_id"] = project_id
        payload["permissionType"] = (
            request.data.get("permissionType")
            or request.data.get("permission_type")
            or "screen"
        )

        with transaction.atomic():
            serializer = CompanyUserScreenPermissionMultiScreenSerializer(
                data=payload,
                context={"update_only": update_only},
            )
            serializer.is_valid(raise_exception=True)
            result = serializer.save()

        cache.clear()

        return Response(
            {
                "created": CompanyUserScreenPermissionSerializer(result["created"], many=True).data,
                "updated": CompanyUserScreenPermissionSerializer(result["updated"], many=True).data,
                "deleted": CompanyUserScreenPermissionSerializer(result["deleted"], many=True).data,
                "created_columns": CompanyUserScreenColumnPermissionSerializer(result.get("created_columns", []), many=True).data,
                "updated_columns": CompanyUserScreenColumnPermissionSerializer(result.get("updated_columns", []), many=True).data,
                "deleted_columns": CompanyUserScreenColumnPermissionSerializer(result.get("deleted_columns", []), many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Queryset
    # ---------------------------------------------------------
    def get_queryset(self):
        company, _ = self._company_from_request(self.request, source="query", required=False)

        qs = CompanyUserScreenPermission.objects.filter(is_deleted=False).select_related(
            "company_id",
            "project_id",
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id",
        )

        if not company:
            if self._is_platform_super_admin():
                pass
            else:
                return qs.none()
        else:
            qs = qs.filter(company_id_id=company.unique_id)

        project_id = self.request.query_params.get("project_id") or self.request.query_params.get("projectId")
        if project_id == "none":
            qs = qs.filter(project_id__isnull=True)
        elif project_id:
            qs = qs.filter(project_id_id=project_id)

        permission_type = (
            self.request.query_params.get("permission_type")
            or self.request.query_params.get("permissionType")
        )
        if permission_type:
            qs = qs.filter(permission_type=permission_type)

        return qs

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "companyId",
                openapi.IN_QUERY,
                description="Company unique_id. Also accepts company_id.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "company_id",
                openapi.IN_QUERY,
                description="Company unique_id.",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={200: CompanyUserScreenPermissionSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=CompanyUserScreenPermissionMultiScreenSerializer,
        responses={200: "Permissions saved successfully", 201: CompanyUserScreenPermissionSerializer},
    )
    def create(self, request, *args, **kwargs):
        if "permissions" in request.data or "userScreens" in request.data or "screens" in request.data:
            return self._sync_nested_permissions(request, update_only=False)

        serializer = CompanyUserScreenPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    # ---------------------------------------------------------
    # Retrieve
    # ---------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    # ---------------------------------------------------------
    # Bulk Sync / Update
    # ---------------------------------------------------------
    @action(detail=False, methods=["post"], url_path=r"bulk-sync-multi-project/(?P<project_id>[^/.]+)")
    def bulk_sync_multi_project(self, request, project_id):
        return self._sync_permissions(request, project_id=project_id, update_only=False)

    @action(detail=False, methods=["post", "put"], url_path=r"update-by-project/(?P<project_id>[^/.]+)")
    def update_by_project(self, request, project_id):
        return self._sync_permissions(request, project_id=project_id, update_only=True)

    # ---------------------------------------------------------
    # By Project + Mainscreen (Shows ALL screens with their actions)
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="by-project-format")
    def by_project_format(self, request):
        return self._by_project_format(request)

    def _by_project_format(self, request):
        company, error = self._company_from_request(request, source="query", required=True)
        if error:
            return error

        project_id = request.query_params.get("project_id") or request.query_params.get("projectId")
        # "none" is the sentinel used by the frontend for company-wide
        # (no-project) permissions, since a URL path segment can't be empty.
        if project_id == "none":
            project_id = None
        mainscreen_id = request.query_params.get("mainscreen_id")
        permission_type = (
            request.query_params.get("permission_type")
            or request.query_params.get("permissionType")
            or "screen"
        )

        if not mainscreen_id:
            return Response(
                {"error": "mainscreen_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔥 CACHE KEY
        cache_key = f"perm_{company.unique_id}_{project_id or 'none'}_{mainscreen_id}_{permission_type}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # 🔥 OPTIMIZED QUERY (NO MODEL LOAD)
        perms = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            project_id_id=project_id,
            mainscreen_id_id=mainscreen_id,
            permission_type=permission_type,
            is_deleted=False,
        ).values(
            "unique_id",
            "userscreen_id_id",
            "userscreenaction_id_id",
            "description",
        )

        column_perms = CompanyUserScreenColumnPermission.objects.filter(
            company_id_id=company.unique_id,
            project_id_id=project_id,
            userscreen_id__mainscreen_id_id=mainscreen_id,
            is_deleted=False,
        ).values(
            "userscreen_id_id",
            "column_id_id",
            "can_view",
        )

        # 🔥 FAST MAP BUILD
        screen_map = defaultdict(lambda: {"actions": [], "columns": []})
        column_map = defaultdict(list)
        description = ""

        for p in perms:
            screen_map[p["userscreen_id_id"]]["actions"].append(p["userscreenaction_id_id"])

            if not description:
                description = p["description"]

        # Build column permissions map
        for cp in column_perms:
            column_map[cp["userscreen_id_id"]].append({
                "column_id": cp["column_id_id"],
                "can_view": cp["can_view"],
            })

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
                "actionIds": screen_map[s["unique_id"]]["actions"] if s["unique_id"] in screen_map else [],
                "columnIds": [col["column_id"] for col in column_map.get(s["unique_id"], [])],
                "columnPermissions": column_map.get(s["unique_id"], []),
                "has_permissions": s["unique_id"] in screen_map,
            }
            for s in screens_qs
        ]

        response_data = {
            "company_id": company.unique_id,
            "project_id": project_id,
            "mainscreen_id": mainscreen_id,
            "permission_type": permission_type,
            "screens": screens,
            "description": description,
        }

        # 🔥 CACHE SAVE (5 min)
        cache.set(cache_key, response_data, timeout=300)

        return Response(response_data)

    # ---------------------------------------------------------
    # All Screens By Project (across all mainscreens)
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="all-screens-by-project")
    def all_screens_by_project(self, request):
        return self._all_screens_by_project(request)

    def _all_screens_by_project(self, request):
        """
        Get ALL screens assigned to a project across all mainscreens.
        Grouped by mainscreen for better visibility.

        Query params:
        - project_id: required
        - company_id: optional (uses middleware scope if available)
        """
        company, error = self._company_from_request(request, source="query", required=True)
        if error:
            return error

        project_id = request.query_params.get("project_id") or request.query_params.get("projectId")
        if not project_id:
            return Response(
                {"error": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get ALL permissions for this company + project (no mainscreen filter)
        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            project_id_id=project_id,
            is_deleted=False,
        ).select_related("mainscreen_id")

        if not qs.exists():
            return Response(
                {
                    "company_id": company.unique_id,
                    "project_id": project_id,
                    "mainscreens": [],
                    "total_screens": 0,
                },
                status=status.HTTP_200_OK,
            )

        # Group by mainscreen
        mainscreen_map = {}

        for perm in qs:
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
                "project_id": project_id,
                "mainscreens": mainscreens,
                "total_screens": total_screens,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Delete By Project + Mainscreen (safe delete)
    # ---------------------------------------------------------
    @action(detail=False, methods=["delete"], url_path=r"delete-by-project/(?P<project_id>[^/.]+)/?")
    def delete_by_project(self, request, project_id):
        # "none" is the sentinel used by the frontend for company-wide
        # (no-project) permissions, since a URL path segment can't be empty.
        resolved_project_id = None if project_id == "none" else project_id
        return self._delete_by_project(request, project_id=resolved_project_id)

    def _delete_by_project(self, request, project_id=None):
        company, error = self._company_from_request(request, source="query", required=True)
        if error:
            return error

        mainscreen_id = request.query_params.get("mainscreen_id")
        permission_type = (
            request.query_params.get("permission_type")
            or request.query_params.get("permissionType")
            or "screen"
        )
        if not mainscreen_id:
            return Response(
                {"error": "mainscreen_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            project_id_id=project_id,
            mainscreen_id_id=mainscreen_id,
            permission_type=permission_type,
            is_deleted=False,
        )

        deleted_count = qs.count()
        if deleted_count > 0:
            qs.update(is_deleted=True, is_active=False)
            CompanyUserScreenColumnPermission.objects.filter(
                company_id_id=company.unique_id,
                project_id_id=project_id,
                userscreen_id__mainscreen_id_id=mainscreen_id,
                is_deleted=False,
            ).update(is_deleted=True, is_active=False)

        return Response(
            {
                "message": "Permissions deleted successfully",
                "deleted_count": deleted_count,
                "project_id": project_id,
                "mainscreen_id": mainscreen_id,
                "permission_type": permission_type,
                "company_id": company.unique_id,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Bulk Upload (CSV)
    # ---------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        try:
            decoded_file = file.read().decode("utf-8")
        except Exception as exc:
            return Response({"error": "Unable to decode CSV file", "detail": str(exc)}, status=400)

        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        if reader.fieldnames:
            reader.fieldnames = [(name or "").strip().lower() for name in reader.fieldnames]

        success_count = 0
        errors: list[dict[str, object]] = []

        company_override = request.data.get("company_id") or request.data.get("companyId")
        project_override = request.data.get("project_id") or request.data.get("projectId")

        order_counters: dict[tuple, int] = {}

        for index, row in enumerate(reader, start=1):
            row = {(key or "").strip().lower(): value for key, value in row.items()}
            try:
                company_id_value = (row.get("company_id") or company_override or "")
                company_id_value = str(company_id_value).strip() if company_id_value else ""

                company = None
                if self._is_platform_super_admin():
                    if not company_id_value:
                        errors.append({"row": index, "error": "company_id is required for superadmin"})
                        continue
                    company = Company.objects.filter(
                        unique_id=company_id_value, is_deleted=False
                    ).first()
                    if not company:
                        errors.append({"row": index, "error": f"Invalid company_id: {company_id_value}"})
                        continue
                else:
                    company = self._company()
                    if not company:
                        errors.append({"row": index, "error": "Failed to resolve company context"})
                        continue

                project_id_value = (row.get("project_id") or project_override or "")
                project_id_value = str(project_id_value).strip() if project_id_value else ""

                project = None
                if project_id_value:
                    project = self._find_project_by_value(company, project_id_value)
                    if not project:
                        errors.append({"row": index, "error": f"Invalid project_id: {project_id_value}"})
                        continue

                mainscreen_value = (row.get("main_screen_id_or_name") or "").strip()
                if not mainscreen_value:
                    errors.append({"row": index, "error": "main_screen_id_or_name is required"})
                    continue
                mainscreen = MainScreen.objects.filter(
                    is_deleted=False
                ).filter(
                    Q(unique_id__iexact=mainscreen_value) | Q(mainscreen_name__iexact=mainscreen_value)
                ).first()
                if not mainscreen:
                    errors.append({"row": index, "error": f"Invalid main_screen_id_or_name: {mainscreen_value}"})
                    continue

                userscreen_value = (row.get("user_screen_id_or_name") or "").strip()
                if not userscreen_value:
                    errors.append({"row": index, "error": "user_screen_id_or_name is required"})
                    continue
                userscreen = UserScreen.objects.filter(
                    is_deleted=False,
                    mainscreen_id_id=mainscreen.unique_id,
                ).filter(
                    Q(unique_id__iexact=userscreen_value) | Q(userscreen_name__iexact=userscreen_value)
                ).first()
                if not userscreen:
                    errors.append({
                        "row": index,
                        "error": (
                            f"Invalid user_screen_id_or_name '{userscreen_value}' "
                            f"for main screen '{mainscreen_value}'"
                        ),
                    })
                    continue

                action_value = (
                    row.get("action_id_or_name")
                    or row.get("action_name")
                    or row.get("variable_name")
                    or ""
                ).strip()
                if not action_value:
                    errors.append({"row": index, "error": "action_id_or_name/action_name/variable_name is required"})
                    continue
                userscreenaction = UserScreenAction.objects.filter(
                    is_deleted=False
                ).filter(
                    Q(unique_id__iexact=action_value)
                    | Q(action_name__iexact=action_value)
                    | Q(variable_name__iexact=action_value)
                ).first()
                if not userscreenaction:
                    errors.append({"row": index, "error": f"Invalid action: {action_value}"})
                    continue

                permission_type = (row.get("permission_type") or "screen").strip().lower()
                if permission_type not in {"screen", "field"}:
                    errors.append({"row": index, "error": "permission_type must be 'screen' or 'field'"})
                    continue

                def _resolve_optional(model, field_value):
                    field_value = (field_value or "").strip()
                    if not field_value:
                        return None
                    obj = model.objects.filter(unique_id=field_value, is_deleted=False).first()
                    return obj

                state = _resolve_optional(State, row.get("state_id"))
                if row.get("state_id") and not state:
                    errors.append({"row": index, "error": f"Invalid state_id: {row.get('state_id')}"})
                    continue

                district = _resolve_optional(District, row.get("district_id"))
                if row.get("district_id") and not district:
                    errors.append({"row": index, "error": f"Invalid district_id: {row.get('district_id')}"})
                    continue

                city = _resolve_optional(City, row.get("city_id"))
                if row.get("city_id") and not city:
                    errors.append({"row": index, "error": f"Invalid city_id: {row.get('city_id')}"})
                    continue

                zone = _resolve_optional(Zone, row.get("zone_id"))
                if row.get("zone_id") and not zone:
                    errors.append({"row": index, "error": f"Invalid zone_id: {row.get('zone_id')}"})
                    continue

                panchayat = _resolve_optional(Panchayat, row.get("panchayat_id"))
                if row.get("panchayat_id") and not panchayat:
                    errors.append({"row": index, "error": f"Invalid panchayat_id: {row.get('panchayat_id')}"})
                    continue

                ward = _resolve_optional(Ward, row.get("ward_id"))
                if row.get("ward_id") and not ward:
                    errors.append({"row": index, "error": f"Invalid ward_id: {row.get('ward_id')}"})
                    continue

                project_unique_id = project.unique_id if project else None

                existing = CompanyUserScreenPermission.objects.filter(
                    company_id_id=company.unique_id,
                    project_id_id=project_unique_id,
                    mainscreen_id_id=mainscreen.unique_id,
                    permission_type=permission_type,
                    userscreen_id_id=userscreen.unique_id,
                    userscreenaction_id_id=userscreenaction.unique_id,
                    is_deleted=False,
                ).first()

                if existing:
                    success_count += 1
                    continue

                counter_key = (company.unique_id, project_unique_id, mainscreen.unique_id)
                order_counters[counter_key] = order_counters.get(counter_key, 0) + 1

                CompanyUserScreenPermission.objects.create(
                    company_id_id=company.unique_id,
                    project_id_id=project_unique_id,
                    mainscreen_id_id=mainscreen.unique_id,
                    permission_type=permission_type,
                    userscreen_id_id=userscreen.unique_id,
                    userscreenaction_id_id=userscreenaction.unique_id,
                    state_id_id=state.unique_id if state else None,
                    district_id_id=district.unique_id if district else None,
                    city_id_id=city.unique_id if city else None,
                    zone_id_id=zone.unique_id if zone else None,
                    panchayat_id_id=panchayat.unique_id if panchayat else None,
                    ward_id_id=ward.unique_id if ward else None,
                    description=(row.get("description") or "").strip() or None,
                    order_no=order_counters[counter_key],
                    is_active=True,
                    is_deleted=False,
                )
                success_count += 1
            except Exception as exc:
                errors.append({"row": index, "error": str(exc)})

        cache.clear()

        return Response({
            "message": "Permission bulk upload completed",
            "success_count": success_count,
            "errors": errors,
        })
