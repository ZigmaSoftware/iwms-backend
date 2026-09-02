from rest_framework import filters
from rest_framework import viewsets
from app.models.staff_creations.designation import Designation
from app.serializers.superadmin.staff_management.designation_serializer import DesignationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class DesignationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Designation.objects.filter(is_deleted=False)
    serializer_class = DesignationSerializer
    lookup_field = "unique_id"
    permission_resource = "Designation"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["designation_name", "designation_group", "description"]
    ordering_fields = ["designation_name", "designation_group", "created_at"]
    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "designations"

    def get_queryset(self):
        queryset = Designation.objects.filter(is_deleted=False)
        status_value = self.request.query_params.get("status")
        group = self.request.query_params.get("designation_group")
        department_id = self.request.query_params.get("department_id")
        if status_value in {"active", "inactive"}:
            queryset = queryset.filter(is_active=status_value == "active")
        if group:
            queryset = queryset.filter(designation_group__iexact=group)
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset
