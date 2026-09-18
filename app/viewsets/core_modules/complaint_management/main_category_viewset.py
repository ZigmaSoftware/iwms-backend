from rest_framework import viewsets, status
from rest_framework.response import Response
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet

from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.serializers.core_modules.complaint_management.maincategory_serializer import MainCategorySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)


class MainCategoryViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = MainCategory.objects.filter(is_deleted=False).order_by("unique_id")
    serializer_class = MainCategorySerializer
    lookup_field = "unique_id"
    filter_backends = [ModelFieldQueryFilter, ModelFieldSearchFilter, SerializerOrderingFilter]

    AUDIT_MODULE = "grivences"
    AUDIT_ENDPOINT = "main-categories"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Main category deleted"}, status=status.HTTP_200_OK)
