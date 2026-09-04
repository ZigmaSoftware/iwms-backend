from django.core.cache import cache
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.screen_managements.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.staff_creations.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.models.staff_creations.staffcreation import Staffcreation
from app.serializers.superadmin.staff_management.staff_access_configuration_serializer import (
    StaffAccessConfigurationSerializer,
)
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.screen_managements.app_module import AppModule
from app.utils.app_feature_grants import (
    CITIZEN_APP_MAINSCREEN,
    ROLE_SCREEN_TEMPLATES,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage


class StaffAccessConfigurationViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    pagination_class = LimitOffsetWithPage
    serializer_class = StaffAccessConfigurationSerializer
    lookup_field = "staff_unique_id"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    search_fields = [
        "staff_id__employee_name",
        "staff_id__staff_unique_id",
        "staff_id__department",
        "staff_id__designation",
    ]
    ordering_fields = ["staff_id__employee_name", "staff_id__staff_unique_id", "staff_id__doj"]

    AUDIT_MODULE = "staff-creations"
    AUDIT_ENDPOINT = "staff-access-configuration"

    permission_resource = "staffaccessconfiguration"

    def get_queryset(self):
        qs = StaffAccessConfiguration.objects.filter(is_deleted=False).select_related(
            "staff_id", "company_id",
        ).prefetch_related(
            "projects", "states", "districts", "cities", "zones", "panchayats", "wards",
        )

        if self._is_platform_super_admin():
            # StaffAccessConfiguration scopes to projects via an M2M
            # ("projects"), not a singular project_id FK, so the generic
            # superadmin filtering in CompanyScopedViewSet.filter_queryset
            # (which only special-cases a plain project_id FK) never applies
            # here — apply the query params explicitly instead.
            company_id_param = (
                self.request.query_params.get("company_id")
                or self.request.query_params.get("company_unique_id")
            )
            project_id_param = (
                self.request.query_params.get("project_id")
                or self.request.query_params.get("project_unique_id")
                or self.request.query_params.get("project")
            )
            if company_id_param:
                qs = qs.filter(company_id_id=company_id_param)
            if project_id_param and project_id_param != "none":
                qs = qs.filter(projects__unique_id=project_id_param)
            return qs

        company = self._company()
        if not company:
            return qs.none()

        qs = qs.filter(company_id_id=company.unique_id)

        if not self._is_admin_user():
            qs = qs.filter(staff_id_id=self.request.user.staff_unique_id)
        elif self._is_project_scoped_admin_user():
            own_project_id = getattr(self.request.user, "project_id_id", None)
            if not own_project_id:
                return qs.none()
            qs = qs.filter(projects__unique_id=own_project_id)

        return qs


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

    @action(detail=False, methods=["get"], url_path="employee-options")
    def employee_options(self, request):
        """Employees for the company (optionally narrowed to a project),
        for the Basic Info tab's employee picker. Each row is flagged with
        whether an active StaffAccessConfiguration already exists for it,
        so the frontend can show/disable "already configured" employees
        instead of letting them be picked again (this form only grants
        access to employees who don't yet have it)."""
        company, error = self._company_from_query(request)
        if error:
            return error

        project_id = (
            request.query_params.get("project_id")
            or request.query_params.get("projectId")
        )

        queryset = Staffcreation.objects.filter(
            company_id_id=company.unique_id,
            is_deleted=False,
            active_status=True,
        ).select_related("personal_details", "staffusertype_id")

        if project_id:
            queryset = queryset.filter(project_id_id=project_id)

        queryset = queryset.order_by("employee_name")

        configured_staff_ids = set(
            StaffAccessConfiguration.objects.filter(
                staff_id_id__in=queryset.values_list("staff_unique_id", flat=True),
                is_deleted=False,
            ).values_list("staff_id_id", flat=True)
        )

        def _personal_details(staff):
            try:
                return staff.personal_details
            except Staffcreation.personal_details.RelatedObjectDoesNotExist:
                return None

        data = [
            {
                "unique_id": staff.staff_unique_id,
                "employee_name": staff.employee_name,
                "mobile_number": getattr(_personal_details(staff), "contact_mobile", None),
                "office_email": getattr(_personal_details(staff), "contact_email", None),
                "doj": staff.doj,
                "staffusertype_id": getattr(staff.staffusertype_id, "unique_id", None),
                "staffusertype_name": getattr(staff.staffusertype_id, "name", None),
                "username": staff.username,
                "active_status": staff.active_status,
                "has_access_configuration": staff.staff_unique_id in configured_staff_ids,
            }
            for staff in queryset[:500]
        ]
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="app-modules")
    def app_modules(self, request):
        """The App Module master, for the tick list on this form.

        Ticking a module decides whether the person may sign into that app at
        all. What they can do inside comes from the ordinary screen
        permissions, which are the same rows that govern web.
        """
        modules = AppModule.objects.filter(is_active=True, is_deleted=False)
        return Response([
            {
                "uniqueId": module.unique_id,
                "moduleKey": module.module_key,
                "surfaceKey": module.surface_key,
                "label": module.label,
                "route": module.route,
                "orderNo": module.order_no,
                "description": module.description,
            }
            for module in modules
        ])

    @action(detail=False, methods=["get"], url_path="role-template")
    def role_template(self, request):
        """The screens a given app role actually calls.

        Backs the "Apply defaults" button. Every one of these is an ordinary
        screen permission the admin could tick by hand — this only saves them
        knowing which ones the Driver app happens to read.
        """
        role = (request.query_params.get("role") or "").strip().lower()
        template = ROLE_SCREEN_TEMPLATES.get(role)
        if template is None:
            return Response(
                {
                    "detail": f"No template for '{role}'.",
                    "available": sorted(ROLE_SCREEN_TEMPLATES),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        wanted = {screen for screens in template.values() for screen in screens}
        rows = UserScreen.objects.filter(
            userscreen_name__in=wanted, is_deleted=False
        ).select_related("mainscreen_id")

        actions = {
            (row.variable_name or row.action_name or "").lower(): row
            for row in UserScreenAction.objects.filter(is_deleted=False)
        }

        screens = []
        for row in rows:
            module_name = row.mainscreen_id.mainscreen_name
            granted = template.get(module_name, {}).get(row.userscreen_name)
            if granted is None:
                for screen_map in template.values():
                    if row.userscreen_name in screen_map:
                        granted = screen_map[row.userscreen_name]
                        break
            screens.append({
                "userScreenId": row.unique_id,
                "userScreenName": row.userscreen_name,
                "mainScreenId": row.mainscreen_id_id,
                "mainScreenName": module_name,
                "actions": [
                    {"actionId": actions[a].unique_id, "actionName": a}
                    for a in (granted or [])
                    if a in actions
                ],
            })

        return Response({"role": role, "screens": screens})

    @action(detail=False, methods=["get"], url_path="available-permissions")
    def available_permissions(self, request):
        company, error = self._company_from_query(request)
        if error:
            return error

        project_ids = request.query_params.getlist("project_id") or request.query_params.getlist("project_id[]")
        if len(project_ids) == 1 and "," in project_ids[0]:
            project_ids = [p.strip() for p in project_ids[0].split(",") if p.strip()]

        base_qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company.unique_id,
            permission_type="screen",
            is_deleted=False,
            is_active=True,
        )

        # No project_id given => company-level permissions only (rows
        # granted directly at the company, not tied to any project).
        if not project_ids:
            rows = base_qs.filter(project_id__isnull=True)
        else:
            rows = base_qs.filter(project_id_id__in=project_ids)

        rows = rows.exclude(
            Q(userscreenaction_id__action_name__iexact="show")
            | Q(userscreenaction_id__variable_name__iexact="show")
        ).select_related(
            "mainscreen_id", "mainscreen_id__mainscreentype_id",
            "userscreen_id", "userscreenaction_id", "project_id",
        ).order_by(
            "project_id__name", "mainscreen_id__order_no", "userscreen_id__order_no", "order_no"
        )

        # Grouped per project (each project's catalog shown as its own
        # section), rather than merged into one flat list — a screen/action
        # enabled differently across projects would otherwise collide.
        # Company-level rows (project_id is null) are grouped under a single
        # "company-wide" pseudo-project entry.
        project_map = {}
        for perm in rows:
            project_entry = project_map.setdefault(
                perm.project_id_id,
                {
                    "projectId": perm.project_id_id,
                    "projectName": perm.project_id.name if perm.project_id_id else "Company-Wide",
                    "mainscreens": {},
                },
            )
            mainscreen_entry = project_entry["mainscreens"].setdefault(
                perm.mainscreen_id_id,
                {
                    "mainScreenId": perm.mainscreen_id_id,
                    "mainScreenName": perm.mainscreen_id.mainscreen_name,
                    # The group this module belongs to. "mobile-app" modules
                    # are app features, not web sidebar routes, so the form
                    # renders them in their own "App Access" tab.
                    "screenType": getattr(
                        perm.mainscreen_id.mainscreentype_id, "type_name", None
                    ),
                    # The citizen app screens are the one group that is not a
                    # web sidebar route; they belong on the customer form.
                    "isCitizenApp": (
                        perm.mainscreen_id.mainscreen_name == CITIZEN_APP_MAINSCREEN
                    ),
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
