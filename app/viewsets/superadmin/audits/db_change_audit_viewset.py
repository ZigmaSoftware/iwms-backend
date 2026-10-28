from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.superadmin.audits.db_change_audit import DbChangeAudit
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.serializers.superadmin.audits.db_change_audit_serializer import (
    DbChangeAuditDetailSerializer,
    DbChangeAuditSerializer,
)
from app.utils.audit_context import is_platform_super_admin
from app.utils.pagination import LimitOffsetWithPage


class DbChangeAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only trail of INSERT/UPDATE/DELETE made on the database directly,
    outside the app (DB Change Audit). Written by the triggers installed by
    app.services.db_change_audit; this viewset never creates or edits them.
    """

    permission_classes = [IsAuthenticated]
    # Matches the "db-change-audit" UserScreen and the "audits" allowlist
    # entry in ModulePermissionMiddleware.
    permission_resource = "DbChangeAudit"
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["changed_at", "table_name", "operation"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DbChangeAuditDetailSerializer
        return DbChangeAuditSerializer

    def _scoped_base_queryset(self):
        """Tenancy gate, matching StaticRouteAuditLogViewSet: a platform super
        admin sees every change; a company user only rows of their company.
        Changes to tables with no company_id column are super admin only."""
        queryset = DbChangeAudit.objects.all().order_by("-changed_at", "-id")
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
        if self.action != "list":
            return queryset
        # The list never needs the row snapshots, which can be large.
        queryset = queryset.defer("old_data", "new_data")
        params = self.request.query_params

        company_id = params.get("company_id") or params.get("company_unique_id")
        if company_id and is_platform_super_admin(self.request.user):
            queryset = queryset.filter(company_id=company_id)

        project_id = params.get("project_id") or params.get("project_unique_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        table_name = params.get("table_name")
        if table_name:
            queryset = queryset.filter(table_name__in=table_name.split(","))

        operation = params.get("operation")
        if operation:
            queryset = queryset.filter(operation__in=operation.upper().split(","))

        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(changed_at__date__gte=date_from)

        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(changed_at__date__lte=date_to)

        search = (params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(object_id__icontains=search)
                | Q(table_name__icontains=search)
                | Q(db_user__icontains=search)
            )

        return queryset

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """Company / project / table / operation choices for the list page's
        dropdowns, drawn from the scoped queryset so a company user is never
        offered another company. Projects narrow to ?company_id= when given."""
        unordered = self._scoped_base_queryset().order_by()

        company_id = request.query_params.get("company_id")
        project_source = unordered.filter(company_id=company_id) if company_id else unordered

        def ids(source, field):
            return [v for v in source.values_list(field, flat=True).distinct() if v]

        def options(model, id_list):
            rows = model.objects.filter(unique_id__in=id_list).values_list("unique_id", "name")
            return sorted(
                ({"unique_id": uid, "name": name or uid} for uid, name in rows),
                key=lambda o: o["name"].lower(),
            )

        return Response({
            "companies": options(Company, ids(unordered, "company_id")),
            "projects": options(Project, ids(project_source, "project_id")),
            "tables": [
                {"unique_id": name, "name": name}
                for name in sorted(ids(unordered, "table_name"))
            ],
            "operations": [
                {"unique_id": value, "name": label}
                for value, label in DbChangeAudit.OPERATION_CHOICES
            ],
        })
