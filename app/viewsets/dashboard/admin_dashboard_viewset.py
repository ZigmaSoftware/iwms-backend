"""Admin Dashboard — the sidebar "Dashboard" page.

GET /api/v1/dashboards/admin/
    ?company_id=   platform super admin only; one id or several, comma
                   separated; omitted = every company
    &project_id=   one id or several, comma separated; omitted = every
                   project the caller may see
    &date=         one day ("day wise"), or
    &from_date=&to_date=   an inclusive range ("date wise")

Granted per staff through the `dashboard / admin-dashboard` screen
(ModulePermissionMiddleware). Company users are always pinned to their own
company, and to the projects their Staff Access Configuration lists.
"""
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.services import dashboard_metrics as metrics


def is_platform_super_admin(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "is_superuser", False)
        and getattr(user, "company_id", None) is None
    )


def allowed_project_ids(user):
    """Projects a company user's access configuration limits them to, or
    None when it lists none (= every project of the company)."""
    staff_id = getattr(user, "staff_unique_id", None)
    if not staff_id:
        return None
    config = StaffAccessConfiguration.objects.filter(
        staff_id=staff_id, is_active=True, is_deleted=False,
    ).first()
    project_ids = config.get_project_ids() if config else []
    return tuple(project_ids) or None


def id_list(params, key):
    """`?key=a,b` and `?key=a&key=b` -> ("a", "b"); blanks dropped."""
    values = []
    for raw in params.getlist(key):
        values += [v.strip() for v in raw.split(",") if v.strip()]
    return tuple(dict.fromkeys(values))


class AdminDashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    permission_resource = "AdminDashboard"

    def _scope(self, request):
        params = request.query_params
        start, end = metrics.parse_range(params)
        user = request.user

        if is_platform_super_admin(user):
            picked_companies = id_list(params, "company_id")
            companies = Company.objects.filter(is_deleted=False).order_by("name")
            if picked_companies:
                companies = companies.filter(unique_id__in=picked_companies)
            project_limit = None
        else:
            picked_companies = ()
            company_id = getattr(user, "company_id", None)
            company_id = getattr(company_id, "unique_id", company_id)
            companies = Company.objects.filter(unique_id=company_id, is_deleted=False)
            project_limit = allowed_project_ids(user)

        company_ids = tuple(companies.values_list("unique_id", flat=True))
        projects = Project.objects.filter(
            company_id__in=company_ids, is_deleted=False,
        ).order_by("name")
        if project_limit is not None:
            projects = projects.filter(unique_id__in=project_limit)

        picked_projects = set(id_list(params, "project_id"))
        visible_projects = list(projects)
        selected = [p for p in visible_projects if p.unique_id in picked_projects]
        if selected:
            project_ids = tuple(p.unique_id for p in selected)
        elif project_limit is not None:
            project_ids = tuple(p.unique_id for p in visible_projects)
        else:
            project_ids = None

        all_companies = is_platform_super_admin(user) and not picked_companies
        scope = metrics.Scope(
            company_ids=None if all_companies else company_ids,
            project_ids=project_ids,
            start=start,
            end=end,
        )
        return scope, list(companies), visible_projects, selected, bool(picked_companies)

    def list(self, request):
        scope, companies, projects, selected, picked_companies = self._scope(request)
        shown_projects = selected or projects
        company_names = {c.unique_id: c.name for c in companies}
        if len(companies) == 1 or picked_companies:
            company_name = ", ".join(c.name for c in companies) or "No company"
        else:
            company_name = "All companies"
        project_name = ", ".join(p.name for p in selected) if selected else "All projects"

        return Response({
            "scope": {
                "company_id": companies[0].unique_id if len(companies) == 1 else None,
                "company_name": company_name,
                "company_ids": [c.unique_id for c in companies] if picked_companies else [],
                "project_id": selected[0].unique_id if len(selected) == 1 else None,
                "project_name": project_name,
                "project_ids": [p.unique_id for p in selected],
                "from_date": scope.start.isoformat(),
                "to_date": scope.end.isoformat(),
                "days": len(scope.days),
            },
            "filters": {
                "can_pick_company": is_platform_super_admin(request.user),
                "companies": [{"id": c.unique_id, "name": c.name} for c in companies]
                if not is_platform_super_admin(request.user)
                else [
                    {"id": c.unique_id, "name": c.name}
                    for c in Company.objects.filter(is_deleted=False).order_by("name")
                ],
                "projects": [
                    {"id": p.unique_id, "name": p.name, "company_id": p.company_id,
                     "company_name": company_names.get(p.company_id, "")}
                    for p in projects
                ],
            },
            "operations": metrics.operations(scope),
            "fleet": metrics.fleet_health(scope),
            "staff": metrics.staff_summary(scope),
            "daily": metrics.daily_series(scope),
            "top": metrics.top_performers(scope),
            "projects": [
                {**row, "company_name": company_names.get(row["company_id"], "")}
                for row in metrics.project_breakdown(scope, shown_projects)
            ],
            "masters": metrics.master_counts(scope, by="project"),
            "generated_at": timezone.now().isoformat(),
        })
