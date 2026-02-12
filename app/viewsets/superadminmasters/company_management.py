from drf_yasg import openapi
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.exceptions import NotFound

from app.models.superadmin_masters.company import Company
from app.permissions.platform import PlatformSuperAdminOnly
from app.serializers.superadmin_masters.company_create_serializer import (
    CompanySerializer,
    PlatformCompanyCreateSerializer,
)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(
    name="list",
    decorator=swagger_auto_schema(
        operation_summary="List companies",
        responses={200: CompanySerializer(many=True)},
    ),
)
@method_decorator(
    name="retrieve",
    decorator=swagger_auto_schema(
        operation_summary="Get company",
        responses={200: CompanySerializer},
    ),
)
@method_decorator(
    name="create",
    decorator=swagger_auto_schema(
        request_body=PlatformCompanyCreateSerializer,
        operation_summary="Create company (metadata only)",
        operation_description=(
            "Creates only the company record. "
            "Admin credentials are not accepted here and must be sent to /superadmin/project/create/ during first project setup."
        ),
        responses={
            201: openapi.Response(
                description="Company created",
                examples={
                    "application/json": {
                        "company": {"unique_id": "CMP-xxxxxxxxxx", "name": "Acme Corp"}
                    }
                },
            )
        },
    ),
)
@method_decorator(
    name="update",
    decorator=swagger_auto_schema(
        request_body=PlatformCompanyCreateSerializer,
        operation_summary="Update company",
        responses={200: CompanySerializer},
    ),
)
@method_decorator(
    name="partial_update",
    decorator=swagger_auto_schema(
        request_body=PlatformCompanyCreateSerializer,
        operation_summary="Patch company",
        responses={200: CompanySerializer},
    ),
)
@method_decorator(
    name="destroy",
    decorator=swagger_auto_schema(
        operation_summary="Delete company",
        responses={204: "No content"},
    ),
)
class PlatformCompanyCreateViewSet(viewsets.ModelViewSet):
    permission_classes = [PlatformSuperAdminOnly]
    queryset = Company.objects.filter(is_deleted=False).order_by("name")
    serializer_class = CompanySerializer
    lookup_field = "unique_id"

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PlatformCompanyCreateSerializer
        return CompanySerializer

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        unique_id = self.kwargs.get(lookup_url_kwarg)
        company = self.get_queryset().filter(unique_id=unique_id).first()
        if not company:
            raise NotFound("Company not found")
        self.check_object_permissions(self.request, company)
        return company
