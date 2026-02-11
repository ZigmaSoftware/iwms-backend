from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import StaffOfficeDetails, StaffPersonalDetails
from app.permissions.platform import PlatformOrCompanyAdminOnly
from app.serializers.superadmin_masters.project_create_serializer import (
    ProjectCreateSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
)


class CompanyProjectCreateViewSet(ViewSet):
    permission_classes = [PlatformOrCompanyAdminOnly]
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

    def _get_project(self, unique_id):
        project = self.get_queryset().filter(unique_id=unique_id).first()
        if not project:
            raise NotFound("Project not found")
        return project

    def _lookup_value(self, pk=None):
        return pk or self.kwargs.get(self.lookup_field)

    @swagger_auto_schema(
        operation_summary="List projects",
        responses={200: ProjectSerializer(many=True)},
    )
    def list(self, request):
        serializer = ProjectSerializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Get project",
        responses={200: ProjectSerializer},
    )
    def retrieve(self, request, pk=None):
        project = self._get_project(self._lookup_value(pk))
        serializer = ProjectSerializer(project)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=ProjectCreateSerializer,
        operation_summary="Create project",
        operation_description=(
            "Creates first/additional project. "
            "Platform super admin must pass company_unique_id. "
            "Admin credential fields are accepted only for first-project setup."
        ),
    )
    @transaction.atomic
    def create(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        is_platform_super_admin = self._is_platform_super_admin(request.user)
        company = self._resolve_company(request.user, data, is_platform_super_admin)

        has_existing_project = Project.objects.filter(company_id=company, is_deleted=False).exists()
        self._validate_admin_payload(data, has_existing_project, is_platform_super_admin)

        project = Project.objects.create(
            company_id=company,
            name=data["name"],
            description=data.get("description"),
            is_active=True,
            is_deleted=False,
        )

        response_data = {"project": ProjectSerializer(project).data}

        if not has_existing_project and self._has_all_admin_fields(data):
            staff = self._create_project_admin(company, project, data)
            response_data["company_admin"] = {
                "unique_id": staff.staff_unique_id,
                "username": staff.username,
            }

        return Response(response_data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        request_body=ProjectUpdateSerializer,
        operation_summary="Update project",
        responses={200: ProjectSerializer},
    )
    def update(self, request, pk=None):
        project = self._get_project(self._lookup_value(pk))
        serializer = ProjectUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project.name = serializer.validated_data["name"]
        project.description = serializer.validated_data.get("description")
        project.save(update_fields=["name", "description"])

        response_serializer = ProjectSerializer(project)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=ProjectUpdateSerializer,
        operation_summary="Patch project",
        responses={200: ProjectSerializer},
    )
    def partial_update(self, request, pk=None):
        project = self._get_project(self._lookup_value(pk))
        serializer = ProjectUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_fields = []
        if "name" in serializer.validated_data:
            project.name = serializer.validated_data["name"]
            update_fields.append("name")
        if "description" in serializer.validated_data:
            project.description = serializer.validated_data["description"]
            update_fields.append("description")

        if update_fields:
            project.save(update_fields=update_fields)

        response_serializer = ProjectSerializer(project)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Delete project",
        responses={204: "No content"},
    )
    def destroy(self, request, pk=None):
        project = self._get_project(self._lookup_value(pk))
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _is_platform_super_admin(self, user):
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is None
        )

    def _resolve_company(self, user, data, is_platform_super_admin):
        company_unique_id = data.get("company_unique_id")
        user_company = getattr(user, "company_id", None)

        if is_platform_super_admin:
            if not company_unique_id:
                raise ValidationError({"company_unique_id": "company_unique_id is required for platform super admin"})
            company = Company.objects.filter(unique_id=company_unique_id).first()
            if not company:
                raise ValidationError({"company_unique_id": "Invalid company_unique_id"})
            return company

        if not user_company:
            raise PermissionDenied("User is not attached to a company")

        if company_unique_id and company_unique_id != getattr(user_company, "unique_id", None):
            raise PermissionDenied("company_unique_id does not match the authenticated company")

        return user_company

    def _validate_admin_payload(self, data, has_existing_project, is_platform_super_admin):
        required_fields = ("admin_username", "admin_password", "admin_employee_name")
        has_any_admin_fields = any(data.get(field) for field in (*required_fields, "admin_email"))
        has_all_admin_fields = self._has_all_admin_fields(data)

        if has_existing_project and has_any_admin_fields:
            raise ValidationError({"admin_username": "Admin credentials are only allowed while creating first project"})

        if not has_existing_project and is_platform_super_admin and not has_all_admin_fields:
            raise ValidationError(
                {
                    "admin_username": "admin_username, admin_password, and admin_employee_name are required for first project",
                }
            )

        if has_any_admin_fields and not has_all_admin_fields:
            raise ValidationError(
                {
                    "admin_username": "admin_username, admin_password, and admin_employee_name must be provided together",
                }
            )

    def _has_all_admin_fields(self, data):
        return bool(
            data.get("admin_username")
            and data.get("admin_password")
            and data.get("admin_employee_name")
        )

    def _create_project_admin(self, company, project, data):
        staff_type, _ = UserType.objects.get_or_create(
            name="staff",
            defaults={"is_active": True, "is_deleted": False},
        )
        admin_role, _ = StaffUserType.objects.get_or_create(
            usertype_id=staff_type,
            name="admin",
            defaults={"is_active": True, "is_deleted": False},
        )

        staff = StaffOfficeDetails.objects.create(
            company_id=company,
            project_id=project,
            employee_name=data["admin_employee_name"],
            username=data["admin_username"],
            password=data["admin_password"],
            user_type_id=staff_type,
            staffusertype_id=admin_role,
            is_staff=False,
            is_active=True,
            is_deleted=False,
        )

        email = data.get("admin_email")
        if email:
            StaffPersonalDetails.objects.create(
                company_id=company,
                project_id=project,
                staff=staff,
                staff_unique_id=staff.staff_unique_id,
                contact_email=email,
            )
        return staff
