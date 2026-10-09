"""Superadmin Dashboard — every company and project on the platform.

GET /api/v1/dashboards/superadmin/?date= | from_date=&to_date=

Platform super admins only (is_superuser with no company). Its catalog
screen, dashboard/superadmin-dashboard, is `superadmin_only`: it shows in the
permission tree, but its route is in PLATFORM_SUPERADMIN_ROUTES, so no grant
opens it for a company user.
"""
from collections import Counter, defaultdict

from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.audits.loginAudit import LoginAudit
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.models.superadmin_masters.auth_user import User
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.permissions.platform import PlatformSuperAdminOnly
from app.services import dashboard_metrics as metrics
from app.utils.permission_catalog import MAINSCREEN_LABELS, SCREEN_LABELS, SCREEN_STRUCTURE

INTEGRATIONS = (
    ("gps", "gps_api_url"),
    ("weighment", "weighment_api_url"),
    ("attendance", "attendance_api_url"),
)


class SuperadminDashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated, PlatformSuperAdminOnly]
    permission_resource = "SuperadminDashboard"

    def list(self, request):
        start, end = metrics.parse_range(request.query_params)
        scope = metrics.Scope(company_ids=None, project_ids=None, start=start, end=end)

        companies = list(Company.objects.filter(is_deleted=False).order_by("name"))
        projects = list(Project.objects.filter(is_deleted=False).order_by("name"))
        company_names = {c.unique_id: c.name for c in companies}
        project_names = {p.unique_id: p.name for p in projects}

        grants = self._permission_grants(company_names, project_names)
        staff_access = self._staff_access(company_names)
        project_rows = metrics.project_breakdown(scope, projects)
        logins = self._logins(scope, company_names)

        return Response({
            "scope": {
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "days": len(scope.days),
            },
            "platform": self._platform(companies, projects),
            "operations": metrics.operations(scope),
            "staff": metrics.staff_summary(scope),
            "fleet": metrics.fleet_health(scope),
            "daily": metrics.daily_series(scope),
            "companies": self._companies(
                companies, projects, project_rows, grants, staff_access, logins,
            ),
            "projects": self._projects(projects, project_rows, grants, company_names),
            "staff_by_role": self._staff_by_role(company_names, project_names),
            "permissions": {
                "catalog": [
                    {
                        "module": module,
                        "label": MAINSCREEN_LABELS.get(module, module),
                        "screens": [
                            {"name": name, "label": SCREEN_LABELS.get(name, name)}
                            for name in screens
                        ],
                    }
                    for module, screens in SCREEN_STRUCTURE.items()
                ],
                "company_grants": grants["rows"],
                "staff_grants": staff_access["by_screen"],
                "changes": self._permission_changes(scope, company_names),
            },
            "activity": logins["summary"],
            "masters": metrics.master_counts(scope, by="company"),
            "generated_at": timezone.now().isoformat(),
        })

    # ------------------------------------------------------------ platform

    def _platform(self, companies, projects):
        catalog_screens = sum(len(s) for s in SCREEN_STRUCTURE.values())
        return {
            "companies": len(companies),
            "companies_active": sum(1 for c in companies if c.is_active),
            "projects": len(projects),
            "projects_active": sum(1 for p in projects if p.is_active),
            "customers": CustomerCreation.objects.filter(is_deleted=False).count(),
            "vehicles": VehicleCreation.objects.filter(is_deleted=False).count(),
            "platform_admins": User.objects.filter(
                is_superuser=True, company_id__isnull=True, is_deleted=False,
            ).count(),
            "staff_access_configs": StaffAccessConfiguration.objects.filter(
                is_deleted=False, is_active=True,
            ).count(),
            "modules": len(SCREEN_STRUCTURE),
            "screens": catalog_screens,
            "screens_seeded": UserScreen.objects.filter(is_deleted=False, is_active=True).count(),
            "app_modules": AppModule.objects.filter(is_deleted=False).count(),
            "integrations": {
                key: sum(1 for p in projects if (getattr(p, field, "") or "").strip())
                for key, field in INTEGRATIONS
            },
        }

    # --------------------------------------------------------- permissions

    def _names(self):
        mains = dict(MainScreen.objects.values_list("unique_id", "mainscreen_name"))
        screens = dict(UserScreen.objects.values_list("unique_id", "userscreen_name"))
        actions = dict(UserScreenAction.objects.values_list("unique_id", "action_name"))
        return mains, screens, actions

    def _permission_grants(self, company_names, project_names):
        """Screens each company/project is enabled for (Companywise User
        Screen Permission). A row with no project applies to every project."""
        mains, screens, actions = self._names()
        tree = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        for company_id, project_id, main_id, screen_id, action_id in (
            CompanyUserScreenPermission.objects.filter(is_deleted=False, is_active=True)
            .values_list("company_id", "project_id", "mainscreen_id", "userscreen_id", "userscreenaction_id")
        ):
            module = mains.get(main_id)
            screen = screens.get(screen_id)
            if not module or not screen:
                continue
            tree[(company_id, project_id)][module][screen].add(actions.get(action_id) or "?")

        catalog = {(m, s) for m, ss in SCREEN_STRUCTURE.items() for s in ss}
        catalog_total = len(catalog)
        rows, by_company, by_project = [], defaultdict(set), defaultdict(set)
        for (company_id, project_id), modules in sorted(
            tree.items(), key=lambda item: (company_names.get(item[0][0], ""), project_names.get(item[0][1], "")),
        ):
            screen_keys = {(m, s) for m, ss in modules.items() for s in ss}
            by_company[company_id] |= screen_keys & catalog
            if project_id:
                by_project[project_id] |= screen_keys & catalog
            rows.append({
                "company_id": company_id,
                "company_name": company_names.get(company_id, company_id),
                "project_id": project_id,
                "project_name": project_names.get(project_id, "All projects") if project_id else "All projects",
                "screens_enabled": len(screen_keys & catalog),
                # Legacy screens outside the catalog are listed but do not
                # count towards coverage, so it never passes 100%.
                "coverage": metrics.pct(len(screen_keys & catalog), catalog_total),
                "modules": [
                    {
                        "module": module,
                        "label": MAINSCREEN_LABELS.get(module, module),
                        "screens": [
                            {"name": s, "label": SCREEN_LABELS.get(s, s), "actions": sorted(a)}
                            for s, a in sorted(ss.items())
                        ],
                    }
                    for module, ss in sorted(modules.items())
                ],
            })
        return {
            "rows": rows,
            "company_screens": {k: len(v) for k, v in by_company.items()},
            "company_modules": {k: len({m for m, _ in v}) for k, v in by_company.items()},
            "project_screens": {k: len(v) for k, v in by_project.items()},
            "catalog_total": catalog_total,
        }

    def _staff_access(self, company_names):
        """Who holds what: staff access configurations per company, and how
        many staff hold `view` on each screen."""
        configs = {
            row["unique_id"]: row
            for row in StaffAccessConfiguration.objects.filter(is_deleted=False, is_active=True)
            .values("unique_id", "company_id", "staff_id")
        }
        mains, screens, actions = self._names()
        holders = defaultdict(lambda: defaultdict(set))  # company -> (module, screen) -> staff
        per_config = Counter()
        for config_id, main_id, screen_id, action_id in (
            StaffAccessConfigurationPermission.objects.filter(
                is_deleted=False, staff_access_configuration_id__in=configs.keys(),
            ).values_list("staff_access_configuration_id", "mainscreen_id", "userscreen_id", "userscreenaction_id")
        ):
            config = configs.get(config_id)
            per_config[config_id] += 1
            if actions.get(action_id) != "view":
                continue
            key = (mains.get(main_id), screens.get(screen_id))
            if None in key:
                continue
            holders[config["company_id"]][key].add(config["staff_id"])

        configured = Counter(c["company_id"] for c in configs.values())
        empty = Counter(c["company_id"] for cid, c in configs.items() if not per_config[cid])
        grants = Counter()
        for cid, c in configs.items():
            grants[c["company_id"]] += per_config[cid]
        by_screen = [
            {
                "company_id": company_id,
                "company_name": company_names.get(company_id, company_id),
                "module": module,
                "module_label": MAINSCREEN_LABELS.get(module, module),
                "screen": screen,
                "screen_label": SCREEN_LABELS.get(screen, screen),
                "staff_with_view": len(staff),
            }
            for company_id, keys in holders.items()
            for (module, screen), staff in sorted(keys.items())
        ]
        return {
            "configured": configured,
            "without_grants": empty,
            "avg_grants": {
                company_id: round(grants[company_id] / n, 1) for company_id, n in configured.items() if n
            },
            "by_screen": by_screen,
        }

    def _permission_changes(self, scope, company_names):
        start_dt, end_dt = scope.window
        changes = PermissionAuditLog.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt)
        per_day = metrics.day_counts(changes.values_list("timestamp", flat=True), scope)
        return {
            "total": changes.count(),
            "by_source": metrics.counts_by(changes, "source"),
            "by_action": metrics.counts_by(changes, "action_type"),
            "by_company": {
                company_names.get(k, k or "Platform"): v
                for k, v in metrics.counts_by(changes, "company_id").items()
            },
            "per_day": [
                {"date": day.isoformat(), "changes": per_day.get(day, 0)} for day in scope.days
            ],
        }

    # ------------------------------------------------------------ activity

    def _logins(self, scope, company_names):
        start_dt, end_dt = scope.window
        logins = LoginAudit.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt)
        ok, failed = Counter(), Counter()
        for stamp, success in logins.values_list("timestamp", "success"):
            day = timezone.localtime(stamp).date()
            (ok if success else failed)[day] += 1
        per_company = {
            row["company_id"]: row
            for row in logins.order_by().values("company_id").annotate(
                ok=Count("pk", filter=Q(success=True)),
                failed=Count("pk", filter=Q(success=False)),
                users=Count("username", distinct=True, filter=Q(success=True)),
            )
        }
        last_login = dict(
            LoginAudit.objects.filter(success=True).order_by().values("company_id")
            .annotate(last=Max("timestamp")).values_list("company_id", "last")
        )
        return {
            "per_company": per_company,
            "last_login": last_login,
            "summary": {
                "logins": sum(ok.values()),
                "failed_logins": sum(failed.values()),
                "active_users": logins.filter(success=True).values("username").distinct().count(),
                "per_day": [
                    {"date": d.isoformat(), "success": ok.get(d, 0), "failed": failed.get(d, 0)}
                    for d in scope.days
                ],
                "by_company": [
                    {
                        "company_id": cid,
                        "company_name": company_names.get(cid, cid or "Platform"),
                        "success": row["ok"],
                        "failed": row["failed"],
                        "users": row["users"],
                    }
                    for cid, row in sorted(per_company.items(), key=lambda i: -i[1]["ok"])
                ],
            },
        }

    # ----------------------------------------------------------- companies

    def _companies(self, companies, projects, project_rows, grants, staff_access, logins):
        staff = StaffcreationOfficeDetails.objects.filter(is_deleted=False)
        staff_rows = {
            row["company_id"]: row
            for row in staff.order_by().values("company_id").annotate(
                total=Count("pk"),
                active=Count("pk", filter=Q(is_active=True, active_status=True)),
                login_enabled=Count("pk", filter=Q(login_enabled=True)),
                pending=Count("pk", filter=Q(approval_status=StaffcreationOfficeDetails.APPROVAL_PENDING)),
            )
        }
        ops = defaultdict(Counter)
        for row in project_rows:
            for key in ("trips", "trips_completed", "trip_logs", "total_kg",
                        "breakdowns", "open_complaints", "customers", "vehicles", "bins"):
                ops[row["company_id"]][key] += row[key]
        project_counts = Counter(p.company_id for p in projects)
        active_projects = Counter(p.company_id for p in projects if p.is_active)
        out = []
        for company in companies:
            cid = company.unique_id
            s = staff_rows.get(cid, {})
            o = ops[cid]
            login = logins["per_company"].get(cid, {})
            last = logins["last_login"].get(cid)
            out.append({
                "company_id": cid,
                "company_name": company.name,
                "is_active": company.is_active,
                "projects": project_counts.get(cid, 0),
                "projects_active": active_projects.get(cid, 0),
                "staff": s.get("total", 0),
                "staff_active": s.get("active", 0),
                "staff_login_enabled": s.get("login_enabled", 0),
                "staff_pending": s.get("pending", 0),
                "staff_configured": staff_access["configured"].get(cid, 0),
                "staff_without_grants": staff_access["without_grants"].get(cid, 0),
                "avg_grants_per_staff": staff_access["avg_grants"].get(cid, 0),
                "screens_enabled": grants["company_screens"].get(cid, 0),
                "modules_enabled": grants["company_modules"].get(cid, 0),
                "screen_coverage": metrics.pct(grants["company_screens"].get(cid, 0), grants["catalog_total"]),
                "customers": o["customers"],
                "vehicles": o["vehicles"],
                "bins": o["bins"],
                "trips": o["trips"],
                "trips_completed": o["trips_completed"],
                "completion_rate": metrics.pct(o["trips_completed"], o["trips"]),
                "trip_logs": o["trip_logs"],
                "total_kg": round(o["total_kg"], 2),
                "breakdowns": o["breakdowns"],
                "open_complaints": o["open_complaints"],
                "logins": login.get("ok", 0),
                "failed_logins": login.get("failed", 0),
                "last_login": last.isoformat() if last else None,
            })
        return out

    def _projects(self, projects, project_rows, grants, company_names):
        rows = {r["project_id"]: r for r in project_rows}
        company_wide = grants["company_screens"]
        out = []
        for project in projects:
            row = dict(rows.get(project.unique_id, {}))
            row.update({
                "company_name": company_names.get(project.company_id, project.company_id),
                "is_active": project.is_active,
                # Project rows plus the company's "all projects" rows.
                "screens_enabled": max(
                    grants["project_screens"].get(project.unique_id, 0),
                    company_wide.get(project.company_id, 0),
                ),
                "integrations": {
                    key: bool((getattr(project, field, "") or "").strip())
                    for key, field in INTEGRATIONS
                },
            })
            out.append(row)
        return out

    def _staff_by_role(self, company_names, project_names):
        role_names = dict(StaffUserType.objects.values_list("unique_id", "name"))
        contractor_names = dict(ContractorUserType.objects.values_list("unique_id", "name"))
        counts = Counter()
        for company_id, project_id, role, contractor in StaffcreationOfficeDetails.objects.filter(
            is_deleted=False,
        ).values_list("company_id", "project_id", "staffusertype_id", "contractorusertype_id"):
            name = role_names.get(role) or contractor_names.get(contractor)
            counts[(company_id, project_id, metrics.pretty_name(name))] += 1
        return [
            {
                "company_id": company_id,
                "company_name": company_names.get(company_id, company_id or "—"),
                "project_id": project_id,
                "project_name": project_names.get(project_id, "—"),
                "role": role,
                "staff": n,
            }
            for (company_id, project_id, role), n in sorted(
                counts.items(),
                key=lambda i: (company_names.get(i[0][0], ""), project_names.get(i[0][1], ""), i[0][2]),
            )
        ]
