from rest_framework import filters
from app.models.masters.block import Block
from app.serializers.masters.block_serializer import BlockSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class BlockViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = BlockSerializer
    lookup_field = "unique_id"
    permission_resource = "Block"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["block_name"]
    ordering_fields = ["block_name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "blocks"

    def get_queryset(self):
        queryset = Block.objects.filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")
        ward_uid = self.request.query_params.get("ward") or self.request.query_params.get("ward_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)
        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)
        if ward_uid:
            queryset = queryset.filter(ward_id__unique_id=ward_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
