from rest_framework import filters, viewsets
from app.models.common_masters.state import State
from app.serializers.superadmin.common_masters.state_serializer import StateSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.location_scope_mixin import LocationScopedViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class StateViewSet(AuditViewSetMixin, LocationScopedViewSetMixin, viewsets.ModelViewSet):
    location_scope_field = "states"
    location_scope_lookup = "unique_id"
    queryset = State.objects.all()   # REQUIRED for DRF basename detection
    serializer_class = StateSerializer
    lookup_field = "unique_id"

    permission_resource = "State"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name"]
    ordering_fields = ["name"]

    AUDIT_MODULE = "common-masters"
    AUDIT_ENDPOINT = "states"

    def get_queryset(self):
        queryset = State.objects.filter(is_deleted=False)\
            .select_related("country_id", "continent_id")\
            .order_by("name")

        country_uid = self.request.query_params.get("country")
        if country_uid:
            queryset = queryset.filter(
                country_id__unique_id=country_uid
            )

        continent_uid = self.request.query_params.get("continent")
        if continent_uid:
            queryset = queryset.filter(
                continent_id__unique_id=continent_uid
            )

        return self.filter_queryset_by_location_scope(queryset)

    def perform_destroy(self, instance):
        instance.delete()
