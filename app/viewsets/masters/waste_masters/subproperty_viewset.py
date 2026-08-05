from rest_framework import filters
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.waste_types.subproperty import SubProperty
from app.serializers.masters.waste_masters.subproperty_serializer import SubPropertySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class SubPropertyViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = SubProperty.objects.filter(is_deleted=False)\
        .select_related("property_id", "company_id", "project_id")\
        .order_by("sub_property_name")

    serializer_class = SubPropertySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["sub_property_name", "property_id__property_name"]
    ordering_fields = ["sub_property_name", "is_active"]
    AUDIT_MODULE = "waste-types"
    AUDIT_ENDPOINT = "subproperties"
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
