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
