from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.superadmin.audits.static_route_audit import StaticRouteAuditLog
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.serializers.superadmin.audits.static_route_audit_serializer import (
    StaticRouteAuditLogDetailSerializer,
    StaticRouteAuditLogSerializer,
)
from app.utils.audit_context import is_platform_super_admin
from app.utils.pagination import LimitOffsetWithPage


class StaticRouteAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only trail of trip plan static route changes (Static Route Audit):
    each row holds the route before and after a save and what changed.
    Written by app.services.static_route.save_plan_static_route; this
    viewset never creates or edits them.
    """

    permission_classes = [IsAuthenticated]
    # Matches the "static-route-audit" UserScreen and the "audits"
    # allowlist entry in ModulePermissionMiddleware.
    permission_resource = "StaticRouteAudit"
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["timestamp", "change_type", "distance_change_meters", "new_version"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return StaticRouteAuditLogDetailSerializer
        return StaticRouteAuditLogSerializer

    def _scoped_base_queryset(self):
        """Tenancy gate, matching PermissionAuditLogViewSet: a platform super
        admin sees every company's changes; a company user only their own."""
        queryset = StaticRouteAuditLog.objects.all().order_by("-timestamp", "-id")
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

        company_id = params.get("company_id") or params.get("company_unique_id")
        if company_id and is_platform_super_admin(self.request.user):
            queryset = queryset.filter(company_id=company_id)

        project_id = params.get("project_id") or params.get("project_unique_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        trip_plan_id = params.get("trip_plan_id")
        if trip_plan_id:
            queryset = queryset.filter(trip_plan_id=trip_plan_id)

        change_type = params.get("change_type")
        if change_type:
            queryset = queryset.filter(change_type__in=change_type.upper().split(","))

        trigger = params.get("trigger")
        if trigger:
            queryset = queryset.filter(trigger__in=trigger.upper().split(","))

        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)

        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        search = (params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(trip_plan_code__icontains=search)
                | Q(trip_plan_id__icontains=search)
                | Q(updated_by__icontains=search)
            )

        return queryset

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """Company / project / trip plan / change type choices for the list
        page's dropdowns, drawn from the scoped queryset so a company user
        is never offered another company. Projects and plans narrow to
        ?company_id= / ?project_id= when given."""
        unordered = self._scoped_base_queryset().order_by()

        company_id = request.query_params.get("company_id")
        project_id = request.query_params.get("project_id")
        project_source = unordered.filter(company_id=company_id) if company_id else unordered
        plan_source = project_source.filter(project_id=project_id) if project_id else project_source

        def ids(source, field):
            return [v for v in source.values_list(field, flat=True).distinct() if v]

        def options(model, id_list):
            rows = model.objects.filter(unique_id__in=id_list).values_list("unique_id", "name")
            return sorted(
                ({"unique_id": uid, "name": name or uid} for uid, name in rows),
                key=lambda o: o["name"].lower(),
            )

        plans = sorted(
            {
                (plan_id, code or plan_id)
                for plan_id, code in plan_source.values_list("trip_plan_id", "trip_plan_code").distinct()
            },
            key=lambda pair: pair[1].lower(),
        )

        return Response({
            "companies": options(Company, ids(unordered, "company_id")),
            "projects": options(Project, ids(project_source, "project_id")),
            "trip_plans": [{"unique_id": uid, "name": name} for uid, name in plans],
            "change_types": [
                {"unique_id": value, "name": label}
                for value, label in StaticRouteAuditLog.CHANGE_TYPE_CHOICES
            ],
            "triggers": [
                {"unique_id": value, "name": label}
                for value, label in StaticRouteAuditLog.TRIGGER_CHOICES
            ],
        })
