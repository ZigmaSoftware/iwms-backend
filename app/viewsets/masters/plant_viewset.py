from rest_framework import filters

from app.models.masters.plant import Plant
from app.serializers.masters.plant_serializer import PlantSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class PlantViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = PlantSerializer
    lookup_field = "unique_id"

    permission_resource = "Plant"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "plants"

    def get_queryset(self):
        queryset = Plant.objects.select_related(
            "company_id",
            "project_id",
        ).filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)

        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
