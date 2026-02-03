from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from api.apps.project import Project


class TenantModelViewSet(viewsets.ModelViewSet):
    """Enterprise-safe default tenant scoping.

    - Platform super admins are blocked from business CRUD endpoints.
    - Staff users are automatically scoped to their company.
    - If X-Project-Id is provided, we include project-specific rows plus company-level rows.

    This keeps behavior predictable and makes tenant isolation hard to bypass.
    """

    project_header = "X-Project-Id"

    def _deny_platform_super_admin(self):
        if getattr(getattr(self, "request", None), "user", None) and getattr(self.request.user, "is_superuser", False):
            raise PermissionDenied("Platform super admin cannot use business endpoints")

    def _company(self):
        return getattr(getattr(self, "request", None), "user", None) and getattr(self.request.user, "company_id", None)

    def _project(self):
        company = self._company()
        if not company:
            return None

        unique_id = self.request.headers.get(self.project_header) or self.request.query_params.get("project")
        if not unique_id and self.request.method in ("POST", "PUT", "PATCH"):
            # Swagger/tests often send project_id in JSON body; accept it, but validate it is in the same company.
            unique_id = self.request.data.get("project_id") or self.request.data.get("project_unique_id")
        if not unique_id:
            return None

        project = Project.objects.filter(unique_id=unique_id, company_id=company).first()
        if not project:
            raise ValidationError({"project_id": "Invalid project_id for this company"})
        return project

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        self._deny_platform_super_admin()

        company = self._company()
        if not company:
            # For business endpoints, non-superusers must be tenant users.
            raise PermissionDenied("Tenant user required")

        # Company scoping (include global rows when present).
        if hasattr(queryset.model, "company_id"):
            queryset = queryset.filter(Q(company_id=company) | Q(company_id__isnull=True))

        project = self._project()
        if project and hasattr(queryset.model, "project_id"):
            queryset = queryset.filter(Q(project_id=project) | Q(project_id__isnull=True))

        return queryset

    def perform_create(self, serializer):
        self._deny_platform_super_admin()
        company = self._company()
        if not company:
            raise PermissionDenied("Tenant user required")

        model = getattr(getattr(serializer, "Meta", None), "model", None)

        save_kwargs = {}
        if model is not None and hasattr(model, "company_id"):
            save_kwargs["company_id"] = company

        project = self._project()
        if project is not None and model is not None and hasattr(model, "project_id"):
            save_kwargs["project_id"] = project

        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        self._deny_platform_super_admin()
        company = self._company()
        if not company:
            raise PermissionDenied("Tenant user required")

        instance = serializer.instance
        model = getattr(getattr(serializer, "Meta", None), "model", None)

        save_kwargs = {}
        if model is not None and hasattr(model, "company_id"):
            # Lock to existing tenant.
            save_kwargs["company_id"] = getattr(instance, "company_id", None) or company

        if model is not None and hasattr(model, "project_id"):
            # If already set, don't allow changing across projects.
            save_kwargs["project_id"] = getattr(instance, "project_id", None) or self._project()

        serializer.save(**save_kwargs)
