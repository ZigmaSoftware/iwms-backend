from drf_yasg import openapi
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.superadmin_masters.company import Company
from app.permissions.platform import PlatformSuperAdminOnly
from app.serializers.superadmin_masters.company_create_serializer import (
    CompanySerializer,
    PlatformCompanyCreateSerializer,
)


@method_decorator(csrf_exempt, name='dispatch')
class PlatformCompanyCreateViewSet(ViewSet):
    permission_classes = [PlatformSuperAdminOnly]
    lookup_field = "unique_id"

    def get_queryset(self):
        return Company.objects.filter(is_deleted=False).order_by("name")

    def _get_company(self, unique_id):
        company = self.get_queryset().filter(unique_id=unique_id).first()
        if not company:
            raise NotFound("Company not found")
        return company

    def _lookup_value(self, pk=None):
        return pk or self.kwargs.get(self.lookup_field)

    @swagger_auto_schema(
        operation_summary="List companies",
        responses={200: CompanySerializer(many=True)},
    )
    def list(self, request):
        serializer = CompanySerializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Get company",
        responses={200: CompanySerializer},
    )
    def retrieve(self, request, pk=None):
        company = self._get_company(self._lookup_value(pk))
        serializer = CompanySerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
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
    )
    def create(self, request):
        serializer = PlatformCompanyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        company = Company.objects.create(
            name=data["name"],
            description=data.get("description"),
        )
        company_data = CompanySerializer(company).data
        return Response(
            {
                "company": company_data,
            },
            status=status.HTTP_201_CREATED,
        )

    @swagger_auto_schema(
        request_body=PlatformCompanyCreateSerializer,
        operation_summary="Update company",
        responses={200: CompanySerializer},
    )
    def update(self, request, pk=None):
        company = self._get_company(self._lookup_value(pk))
        serializer = PlatformCompanyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company.name = serializer.validated_data["name"]
        company.description = serializer.validated_data.get("description")
        company.save(update_fields=["name", "description"])

        response_serializer = CompanySerializer(company)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=PlatformCompanyCreateSerializer,
        operation_summary="Patch company",
        responses={200: CompanySerializer},
    )
    def partial_update(self, request, pk=None):
        company = self._get_company(self._lookup_value(pk))
        serializer = PlatformCompanyCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_fields = []
        if "name" in serializer.validated_data:
            company.name = serializer.validated_data["name"]
            update_fields.append("name")
        if "description" in serializer.validated_data:
            company.description = serializer.validated_data["description"]
            update_fields.append("description")

        if update_fields:
            company.save(update_fields=update_fields)

        response_serializer = CompanySerializer(company)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Delete company",
        responses={204: "No content"},
    )
    def destroy(self, request, pk=None):
        company = self._get_company(self._lookup_value(pk))
        company.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
