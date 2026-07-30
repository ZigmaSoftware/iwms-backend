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
    serializer_class = StaffAccessConfigurationSerializer
    lookup_field = "staff_unique_id"

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staff-access-configuration"

    permission_resource = "staffaccessconfiguration"

    def get_queryset(self):
        qs = StaffAccessConfiguration.objects.filter(is_deleted=False).select_related(
            "staff_id", "company_id", "project_id",
            "state_id", "district_id", "city_id", "zone_id", "panchayat_id", "ward_id",
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

        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"error": "project_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        rows = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            project_id_id=project_id,
            permission_type="screen",
            is_deleted=False,
            is_active=True,
        ).exclude(
            Q(userscreenaction_id__action_name__iexact="show")
            | Q(userscreenaction_id__variable_name__iexact="show")
        ).select_related("mainscreen_id", "userscreen_id", "userscreenaction_id").order_by(
            "mainscreen_id__order_no", "userscreen_id__order_no", "order_no"
        )

        mainscreen_map = {}
        for perm in rows:
            mainscreen_id = perm.mainscreen_id_id
            mainscreen_entry = mainscreen_map.setdefault(
                mainscreen_id,
                {
                    "mainScreenId": mainscreen_id,
                    "mainScreenName": perm.mainscreen_id.mainscreen_name,
                    "screens": {},
                },
            )
            screen_entry = mainscreen_entry["screens"].setdefault(
                perm.userscreen_id_id,
                {
                    "userScreenId": perm.userscreen_id_id,
                    "userScreenName": perm.userscreen_id.userscreen_name,
                    "actions": [],
                },
            )
            screen_entry["actions"].append({
                "actionId": perm.userscreenaction_id_id,
                "actionName": perm.userscreenaction_id.action_name,
            })

        mainscreens = []
        for entry in mainscreen_map.values():
            entry["screens"] = list(entry["screens"].values())
            mainscreens.append(entry)

        return Response({
            "company_id": company.unique_id,
            "project_id": project_id,
            "mainscreens": mainscreens,
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
