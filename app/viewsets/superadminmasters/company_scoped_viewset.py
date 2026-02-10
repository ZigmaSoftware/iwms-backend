from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from app.models.superadmin_masters.project import Project


class CompanyScopedViewSet(viewsets.ModelViewSet):
    """Enterprise-safe default company scoping.

    - Staff users are automatically scoped to their company.
    - If X-Project-Id is provided, we include project-specific rows plus company-level rows.
    - Platform super admins may bypass company scoping and manage everything.

    This keeps behavior predictable and makes company isolation hard to bypass.
    """

    project_header = "X-Project-Id"

    def _is_platform_super_admin(self):
        user = getattr(getattr(self, "request", None), "user", None)
        if not user:
            return False

        # Treat as platform super admin only when no company is attached.
        if getattr(user, "is_superuser", False) and not getattr(user, "company_id", None):
            return True

        payload = getattr(self.request, "jwt_payload", {}) or {}
        role = (payload.get("role") or "").lower()
        user_type = (payload.get("user_type") or "").lower()
        has_company = payload.get("company_unique_id") or getattr(user, "company_id", None)

        return user_type == "platform" and role == "superadmin" and not has_company

    def _company(self):
        user = getattr(getattr(self, "request", None), "user", None)
        if not user:
            return None

        company = getattr(user, "company_id", None)
        if company:
            return company

        staff = getattr(user, "staff_id", None)
        if staff and getattr(staff, "company_id", None):
            return staff.company_id

        customer = getattr(user, "customer_id", None)
        if customer and getattr(customer, "company_id", None):
            return customer.company_id

        return None

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

        if self._is_platform_super_admin():
            return queryset

        company = self._company()
        if not company:
            raise PermissionDenied("Company user required")

        # Company scoping (include global rows when present).
        if hasattr(queryset.model, "company_id"):
            queryset = queryset.filter(Q(company_id=company) | Q(company_id__isnull=True))

        project = self._project()
        if project and hasattr(queryset.model, "project_id"):
            queryset = queryset.filter(Q(project_id=project) | Q(project_id__isnull=True))

        return queryset

    def perform_create(self, serializer):
        if self._is_platform_super_admin():
            return serializer.save()

        company = self._company()
        if not company:
            raise PermissionDenied("Company user required")

        model = getattr(getattr(serializer, "Meta", None), "model", None)

        save_kwargs = {}
        if model is not None and hasattr(model, "company_id"):
            save_kwargs["company_id"] = company

        project = self._project()
        if project is not None and model is not None and hasattr(model, "project_id"):
            save_kwargs["project_id"] = project

        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        if self._is_platform_super_admin():
            return serializer.save()

        company = self._company()
        if not company:
            raise PermissionDenied("Company user required")

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
