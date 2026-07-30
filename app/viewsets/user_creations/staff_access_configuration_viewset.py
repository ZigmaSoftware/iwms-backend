from django.core.cache import cache
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.screen_managements.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.user_creations.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.serializers.user_creations.staff_access_configuration_serializer import (
    StaffAccessConfigurationSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class StaffAccessConfigurationViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    pagination_class = None
    serializer_class = StaffAccessConfigurationSerializer
    lookup_field = "staff_unique_id"

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staff-access-configuration"

    permission_resource = "staffaccessconfiguration"

    def get_queryset(self):
        qs = StaffAccessConfiguration.objects.filter(is_deleted=False).select_related(
            "staff_id", "company_id",
        ).prefetch_related(
            "projects", "states", "districts", "cities", "zones", "panchayats", "wards",
        )

        if self._is_platform_super_admin():
            return qs

        company = self._company()
        if not company:
            return qs.none()

        return qs.filter(company_id_id=company.unique_id)


    def get_object(self):
        staff_unique_id = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        obj = self.get_queryset().filter(staff_id_id=staff_unique_id).first()
        if not obj:
            from django.http import Http404
            raise Http404
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        serializer.save()
        cache.clear()

    def perform_update(self, serializer):
        serializer.save()
        cache.clear()

    def perform_destroy(self, instance):
        instance.delete()
        cache.clear()

    @action(detail=False, methods=["get"], url_path="available-permissions")
    def available_permissions(self, request):
        company, error = self._company_from_query(request)
        if error:
            return error

        project_ids = request.query_params.getlist("project_id") or request.query_params.getlist("project_id[]")
        if len(project_ids) == 1 and "," in project_ids[0]:
            project_ids = [p.strip() for p in project_ids[0].split(",") if p.strip()]

        # No project_id given => company-wide (every project under the
        # company), matching the "company only mandatory" scope semantics.
        if not project_ids:
            from app.models.superadmin_masters.project import Project
            project_ids = list(
                Project.objects.filter(company_id_id=company.unique_id, is_deleted=False)
                .order_by("name")
                .values_list("unique_id", flat=True)
            )

        rows = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            project_id_id__in=project_ids,
            permission_type="screen",
            is_deleted=False,
            is_active=True,
        ).exclude(
            Q(userscreenaction_id__action_name__iexact="show")
            | Q(userscreenaction_id__variable_name__iexact="show")
        ).select_related(
            "mainscreen_id", "userscreen_id", "userscreenaction_id", "project_id",
        ).order_by(
            "project_id__name", "mainscreen_id__order_no", "userscreen_id__order_no", "order_no"
        )

        # Grouped per project (each project's catalog shown as its own
        # section), rather than merged into one flat list — a screen/action
        # enabled differently across projects would otherwise collide.
        project_map = {}
        for perm in rows:
            project_entry = project_map.setdefault(
                perm.project_id_id,
                {
                    "projectId": perm.project_id_id,
                    "projectName": perm.project_id.name,
                    "mainscreens": {},
                },
            )
            mainscreen_entry = project_entry["mainscreens"].setdefault(
                perm.mainscreen_id_id,
                {
                    "mainScreenId": perm.mainscreen_id_id,
                    "mainScreenName": perm.mainscreen_id.mainscreen_name,
                    "screens": {},
                },
            )
            screen_entry = mainscreen_entry["screens"].setdefault(
                perm.userscreen_id_id,
                {
                    "userScreenId": perm.userscreen_id_id,
                    "userScreenName": perm.userscreen_id.userscreen_name,
                    "actions": {},
                },
            )
            screen_entry["actions"][perm.userscreenaction_id_id] = {
                "actionId": perm.userscreenaction_id_id,
                "actionName": perm.userscreenaction_id.action_name,
            }

        projects = []
        for project_entry in project_map.values():
            mainscreens = []
            for mainscreen_entry in project_entry["mainscreens"].values():
                screens = []
                for screen_entry in mainscreen_entry["screens"].values():
                    screen_entry["actions"] = list(screen_entry["actions"].values())
                    screens.append(screen_entry)
                mainscreen_entry["screens"] = screens
                mainscreens.append(mainscreen_entry)
            project_entry["mainscreens"] = mainscreens
            projects.append(project_entry)

        return Response({
            "company_id": company.unique_id,
            "project_ids": project_ids,
            "projects": projects,
        })

    def _company_from_query(self, request):
        scoped_company = self._company()
        if scoped_company:
            return scoped_company, None

        company_id = (
            request.query_params.get("company_id")
            or request.query_params.get("companyId")
        )
        if not company_id:
            return None, Response(
                {"error": "company_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        from app.models.superadmin_masters.company import Company
        company = Company.objects.filter(unique_id=company_id).first()
        if not company:
            return None, Response({"error": "Invalid company"}, status=status.HTTP_400_BAD_REQUEST)
        return company, None
