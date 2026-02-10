from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.permissions.platform import PlatformSuperAdminOnly, CompanyAdminOnly
from app.serializers.superadmin_masters.project_create_serializer import ProjectCreateSerializer


class PlatformFirstProjectCreateViewSet(ViewSet):
    permission_classes = [PlatformSuperAdminOnly]

    @swagger_auto_schema(request_body=ProjectCreateSerializer)
    def create(self, request, company_unique_id=None):
        if not company_unique_id:
            raise NotFound("Company not found")

        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = Company.objects.filter(unique_id=company_unique_id).first()
        if not company:
            raise NotFound("Company not found")

        if Project.objects.filter(company_id=company).exists():
            raise PermissionDenied("First project already exists; use company-admin flow for additional projects")

        project = Project.objects.create(
            company_id=company,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description"),
        )

        return Response(
            {"project": {"unique_id": project.unique_id, "name": project.name}},
            status=status.HTTP_201_CREATED,
        )


class CompanyAdditionalProjectCreateViewSet(ViewSet):
    permission_classes = [CompanyAdminOnly]

    @swagger_auto_schema(request_body=ProjectCreateSerializer)
    def create(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = getattr(request.user, "company_id", None)
        if not company:
            raise PermissionDenied("User is not attached to a company")

        if not Project.objects.filter(company_id=company).exists():
            raise PermissionDenied("Company has no project yet; first project must be created by platform super admin")

        project = Project.objects.create(
            company_id=company,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description"),
        )

        return Response(
            {"project": {"unique_id": project.unique_id, "name": project.name}},
            status=status.HTTP_201_CREATED,
        )
