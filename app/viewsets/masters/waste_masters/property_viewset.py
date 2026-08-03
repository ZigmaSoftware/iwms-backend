from rest_framework import filters
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.waste_types.property import Property
from app.serializers.masters.waste_masters.property_serializer import PropertySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class PropertyViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    lookup_field = "unique_id"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["property_name"]
    ordering_fields = ["property_name", "is_active"]

    AUDIT_MODULE = "waste-types"
    AUDIT_ENDPOINT = "properties"

    def get_queryset(self):
        queryset = Property.objects.filter(is_deleted=False)
        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id__unique_id=project_id)
        return queryset

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
