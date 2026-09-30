from django.utils.dateparse import parse_date
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.serializers.superadmin.audits.permission_audit_serializer import (
    PermissionAuditLogSerializer,
)
from app.utils.audit_context import is_platform_super_admin
from app.utils.pagination import LimitOffsetWithPage


class PermissionAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only trail of screen/action permission grant changes (User Access
    Audit). Rows are written only by the post_save signals in
    app/signals/permission_signals.py, one per grant source (company screen
    and column permissions, Staff and Customer Access Configuration); this
    viewset never creates or edits them.
    """

    permission_classes = [IsAuthenticated]
    # Matches the "permission-audit" UserScreen and the "audits" allowlist
    # entry in ModulePermissionMiddleware.
    permission_resource = "PermissionAudit"
    serializer_class = PermissionAuditLogSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "source",
        "target_id",
        "app_module_id",
        "column_id",
        "company_id",
        "project_id",
        "mainscreen_id",
        "userscreen_id",
        "userscreenaction_id",
        "updated_by",
        "action_type",
    ]
    ordering_fields = ["timestamp", "action_type"]

    def _scoped_base_queryset(self):
        """
        Tenancy gate, matching CommonAuditViewSet: a platform super admin
        sees every company's grant changes; a company user only their own.
        """
        queryset = PermissionAuditLog.objects.all().order_by("-timestamp")
        user = self.request.user

        if is_platform_super_admin(user):
            return queryset

        company = getattr(user, "company_id", None)
        company_uid = str(getattr(company, "unique_id", company) or "") or None

        if not company_uid:
            raise PermissionDenied("Company user required")

        return queryset.filter(company_id=company_uid)

    def get_queryset(self):
        queryset = self._scoped_base_queryset()
        params = self.request.query_params

        # Cross-company filter is superadmin-only; for a company user the
        # base queryset is already pinned, so this param cannot widen it.
        company_id = params.get("company_id") or params.get("company_unique_id")
        if company_id and is_platform_super_admin(self.request.user):
            queryset = queryset.filter(company_id=company_id)

        project_id = params.get("project_id") or params.get("project_unique_id")
        if project_id:
            # "none" = company-wide grants that belong to no project.
            if project_id == "none":
                queryset = queryset.filter(project_id__isnull=True)
            else:
                queryset = queryset.filter(project_id=project_id)

        mainscreen_id = params.get("mainscreen_id")
        if mainscreen_id:
            queryset = queryset.filter(mainscreen_id__in=mainscreen_id.split(","))

        source = params.get("source")
        if source:
            queryset = queryset.filter(source__in=source.upper().split(","))

        target_id = params.get("target_id")
        if target_id:
            queryset = queryset.filter(target_id=target_id)

        action_type = params.get("action_type")
        if action_type:
            queryset = queryset.filter(action_type=action_type.upper())

        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)

        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        return queryset

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """
        Company/project/main-screen choices for the list page's dropdowns,
        drawn from the scoped queryset so a company user is never offered
        another company. Projects narrow to ?company_id= when given.
        """
        # order_by() clears Meta.ordering so DISTINCT applies to the column.
        unordered = self._scoped_base_queryset().order_by()

        def ids(field, source=unordered):
            return [
                v for v in source.values_list(field, flat=True).distinct() if v
            ]

        def options(model, id_list, name_field):
            rows = model.objects.filter(unique_id__in=id_list).values_list(
                "unique_id", name_field
            )
            return sorted(
                ({"unique_id": uid, "name": name or uid} for uid, name in rows),
                key=lambda o: o["name"].lower(),
            )

        company_id = request.query_params.get("company_id") or request.query_params.get(
            "company_unique_id"
        )
        project_source = (
            unordered.filter(company_id=company_id) if company_id else unordered
        )

        return Response({
            "companies": options(Company, ids("company_id"), "name"),
            "projects": options(Project, ids("project_id", project_source), "name"),
            "mainscreens": options(MainScreen, ids("mainscreen_id"), "mainscreen_name"),
            "sources": [
                {"unique_id": value, "name": label}
                for value, label in PermissionAuditLog.SOURCE_CHOICES
            ],
        })
