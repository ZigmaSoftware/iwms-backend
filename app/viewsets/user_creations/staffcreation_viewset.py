from django.db import transaction

from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet

from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.staffcreation_serializer import StaffcreationSerializer
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class StaffcreationViewset(CompanyScopedViewSet):
    queryset = Staffcreation.objects.select_related("personal_details").all()
    serializer_class = StaffcreationSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_resource = "StaffCreation"
    lookup_field = "staff_unique_id"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "employee_name",
        "staff_unique_id",
        "site_name",
        "department",
        "designation",
    ]
    ordering_fields = ["staff_unique_id", "employee_name", "created_at"]

    def get_queryset(self):
        queryset = Staffcreation.objects.select_related("personal_details")

        site_name = self.request.query_params.get("site_name", None)
        employee_name = self.request.query_params.get("employee_name", None)
        active_status = self.request.query_params.get("active_status", None)
        salary_type = self.request.query_params.get("salary_type", None)

        if site_name:
            queryset = queryset.filter(site_name__icontains=site_name)

        if employee_name:
            queryset = queryset.filter(employee_name__icontains=employee_name)

        if active_status in ["0", "1"]:
            queryset = queryset.filter(active_status=active_status == "1")

        if salary_type:
            queryset = queryset.filter(salary_type__icontains=salary_type)

        return queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            with transaction.atomic():
                # Handle platform superadmin vs company user
                if self._is_platform_super_admin():
                    # Get company from request data for platform superadmin
                    company_unique_id = request.data.get("company_id")
                    if not company_unique_id:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({"company_id": "company_id is required"})
                    
                    company = Company.objects.filter(unique_id=company_unique_id).first()
                    if not company:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({"company_id": "Invalid company_id"})
                    
                    # Get project from request data
                    project_unique_id = (
                        request.headers.get(self.project_header)
                        or request.data.get("project_id")
                        or request.data.get("project_unique_id")
                    )
                    if project_unique_id:
                        project = Project.objects.filter(
                            unique_id=project_unique_id,
                            company_id=company
                        ).first()
                        if not project:
                            from rest_framework.exceptions import ValidationError
                            raise ValidationError({"project_id": "Invalid project_id for this company"})
                    else:
                        # Get the first active project for the company as default
                        project = Project.objects.filter(
                            company_id=company,
                            is_active=True,
                            is_deleted=False
                        ).first()
                        if not project:
                            from rest_framework.exceptions import ValidationError
                            raise ValidationError({"project_id": "project_id is required - no active project found for this company"})
                else:
                    # Company user - use scoped methods
                    company = self._company()
                    if not company:
                        from rest_framework.exceptions import PermissionDenied
                        raise PermissionDenied("Company user required")
                    
                    project = self._project()
                    if not project:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({"project_id": "project_id is required"})

                serializer.save(
                    company_id=company,
                    project_id=project,
                )
            return Response(
                {"status": True, "message": "Staff Created Successfully"},
                status=status.HTTP_201_CREATED
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=kwargs.pop("partial", False),
        )

        if serializer.is_valid():
            with transaction.atomic():
                company = getattr(instance, "company_id", None) or self._company()
                project = getattr(instance, "project_id", None) or self._project()
                serializer.save(
                    company_id=company,
                    project_id=project,
                )
            return Response(
                {"status": True, "message": "Staff Updated Successfully"},
                status=status.HTTP_200_OK
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()

        return Response(
            {"status": True, "message": "Staff Deleted Successfully"},
            status=status.HTTP_200_OK
        )
