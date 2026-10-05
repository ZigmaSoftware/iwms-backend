from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.services.audit_dashboard import TRAILS, in_range, parse_days, summary as build_summary, window
from app.utils.audit_context import is_platform_super_admin
from app.utils.pagination import LimitOffsetWithPage


class AuditDashboardViewSet(viewsets.ViewSet):
    """
    Read-only Audit Dashboard over the five audit trails. ?module= picks the
    trail (common, login, access, route, complaint); ?days= the window
    (7, 30 or 90). Assembled on read by app.services.audit_dashboard.

        GET audit-dashboard/summary/          KPIs, per-day trend, breakdown
        GET audit-dashboard/records/          the window's rows, paginated
        GET audit-dashboard/filter-options/   company / project choices
    """

    permission_classes = [IsAuthenticated]
    # Matches the "audit-dashboard" UserScreen and the "audits" allowlist
    # entry in ModulePermissionMiddleware.
    permission_resource = "AuditDashboard"

    def _company_uid(self):
        company = getattr(self.request.user, "company_id", None)
        return str(getattr(company, "unique_id", company) or "") or None

    def _trail(self):
        key = self.request.query_params.get("module") or "common"
        trail = TRAILS.get(key)
        if trail is None:
            raise ValidationError({"module": f"Choose one of: {', '.join(TRAILS)}."})
        return trail

    def _scoped(self, trail):
        """Tenancy gate, matching the audit list viewsets: a platform super
        admin sees every company; a company user only their own, whatever
        ?company_id= says."""
        queryset = trail.base_queryset()
        params = self.request.query_params

        if is_platform_super_admin(self.request.user):
            company_id = params.get("company_id")
            if company_id:
                queryset = queryset.filter(**{trail.company_field: company_id})
        else:
            company_uid = self._company_uid()
            if not company_uid:
                raise PermissionDenied("Company user required")
            queryset = queryset.filter(**{trail.company_field: company_uid})

        project_id = params.get("project_id")
        if project_id:
            queryset = queryset.filter(**{trail.project_field: project_id})
        return queryset

    @action(detail=False, methods=["get"])
    def summary(self, request):
        trail = self._trail()
        days = parse_days(request.query_params.get("days"))
        return Response(build_summary(trail, self._scoped(trail), days))

    @action(detail=False, methods=["get"])
    def records(self, request):
        trail = self._trail()
        days = parse_days(request.query_params.get("days"))
        _, _, start, end, _ = window(days)
        queryset = in_range(trail, self._scoped(trail), start, end)

        search = (request.query_params.get("search") or "").strip()
        if search:
            queryset = trail.search(queryset, search)

        paginator = LimitOffsetWithPage()
        page = paginator.paginate_queryset(trail.ordered(queryset), request, view=self)
        return paginator.get_paginated_response(trail.rows(page))

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """Companies and projects for the scope dropdown. A company user is
        only ever offered their own company's projects."""
        projects = Project.objects.filter(is_deleted=False)
        if is_platform_super_admin(request.user):
            companies = Company.objects.filter(is_deleted=False)
        else:
            company_uid = self._company_uid()
            if not company_uid:
                raise PermissionDenied("Company user required")
            companies = Company.objects.filter(unique_id=company_uid)
            projects = projects.filter(company_id=company_uid)

        company_names = dict(companies.values_list("unique_id", "name"))
        return Response({
            "companies": sorted(
                ({"unique_id": uid, "name": name} for uid, name in company_names.items()),
                key=lambda o: (o["name"] or "").lower(),
            ),
            "projects": sorted(
                (
                    {
                        "unique_id": uid,
                        "name": name,
                        "company_id": company_id,
                        "company_name": company_names.get(company_id),
                    }
                    for uid, name, company_id in projects.values_list("unique_id", "name", "company_id")
                    if company_id in company_names
                ),
                key=lambda o: ((o["company_name"] or "").lower(), (o["name"] or "").lower()),
            ),
        })
