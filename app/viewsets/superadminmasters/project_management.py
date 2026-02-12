from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.exceptions import NotFound

from app.models.superadmin_masters.project import Project
from app.permissions.platform import PlatformOrCompanyAdminOnly
from app.serializers.superadmin_masters.project_create_serializer import (
    ProjectCreateSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
)

class CompanyProjectCreateViewSet(viewsets.ModelViewSet):
    permission_classes = [PlatformOrCompanyAdminOnly]
    queryset = Project.objects.select_related("company_id").filter(is_deleted=False).order_by("name")
    serializer_class = ProjectSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = Project.objects.select_related("company_id").filter(is_deleted=False).order_by("name")
        user = getattr(self.request, "user", None)
        if self._is_platform_super_admin(user):
            company_unique_id = self.request.query_params.get("company_unique_id")
            if company_unique_id:
                queryset = queryset.filter(company_id__unique_id=company_unique_id)
            return queryset

        company = getattr(user, "company_id", None)
        if not company:
            return Project.objects.none()
        return queryset.filter(company_id=company)

    def get_serializer_class(self):
        if self.action == "create":
            return ProjectCreateSerializer
        if self.action in {"update", "partial_update"}:
            return ProjectUpdateSerializer
        return ProjectSerializer

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        unique_id = self.kwargs.get(lookup_url_kwarg)
        project = self.get_queryset().filter(unique_id=unique_id).first()
        if not project:
            raise NotFound("Project not found")
        self.check_object_permissions(self.request, project)
        return project

    @staticmethod
    def _is_platform_super_admin(user):
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )
