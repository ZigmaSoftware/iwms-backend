# from drf_yasg import openapi
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
# from drf_yasg.utils import swagger_auto_schema
# from rest_framework import viewsets
# from rest_framework.exceptions import NotFound

# from app.models.superadmin_masters.company import Company
# from app.permissions.platform import PlatformSuperAdminOnly
# from app.serializers.superadmin_masters.company_create_serializer import (
#     CompanySerializer,
#     PlatformCompanyCreateSerializer,
# )


# class PlatformCompanyCreateViewSet(viewsets.ModelViewSet):
#     permission_classes = [PlatformSuperAdminOnly]
#     queryset = Company.objects.filter(is_deleted=False).order_by("name")
#     serializer_class = CompanySerializer
#     lookup_field = "unique_id"

#     def get_serializer_class(self):
#         if self.action in {"create", "update", "partial_update"}:
#             return PlatformCompanyCreateSerializer
#         return CompanySerializer

#     def get_object(self):
#         lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
#         unique_id = self.kwargs.get(lookup_url_kwarg)
#         company = self.get_queryset().filter(unique_id=unique_id).first()
#         if not company:
#             raise NotFound("Company not found")
#         self.check_object_permissions(self.request, company)
#         return company


from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from app.permissions.platform import PlatformOrCompanyAdminOnly
from app.models.superadmin_masters.company import Company
from app.serializers.superadmin_masters.company_create_serializer import (
    CompanySerializer,
    PlatformCompanyCreateSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin

class PlatformCompanyCreateViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [PlatformOrCompanyAdminOnly]
    serializer_class = CompanySerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "superadmin-masters"
    AUDIT_ENDPOINT = "companies"

    # 🔹 Role-Based Queryset
    def get_queryset(self):
        user = self.request.user

        # Platform super admin
        if getattr(user, "is_superuser", False) and getattr(user, "company_id", None) is None:
            return Company.objects.filter(is_deleted=False).order_by("name")

        # Company admin
        role = getattr(getattr(user, "staffusertype_id", None), "name", "")
        if (
            not getattr(user, "is_superuser", False)
            and getattr(user, "company_id", None) is not None
            and (role or "").lower() == "admin"
        ):
            return Company.objects.filter(
                unique_id=user.company_id.unique_id,
                is_deleted=False,
            )

        return Company.objects.none()
    # 🔹 Restrict Modify Access
    def get_permissions(self):
        user = self.request.user

        if getattr(user, "role", None) == "admin" and self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            raise PermissionDenied("Admins are not allowed to modify companies.")

        return super().get_permissions()

    # 🔹 Dynamic Serializer
    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PlatformCompanyCreateSerializer
        return CompanySerializer

    # 🔹 Safe Object Fetch
    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        unique_id = self.kwargs.get(lookup_url_kwarg)

        company = self.get_queryset().filter(unique_id=unique_id).first()
        if not company:
            raise NotFound("Company not found")

        return company