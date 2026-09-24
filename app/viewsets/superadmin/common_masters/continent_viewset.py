from rest_framework import filters, viewsets
from app.models.common_masters.continent import Continent
from app.serializers.superadmin.common_masters.continent_serializer import ContinentSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.location_scope_mixin import LocationScopedViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class ContinentViewSet(AuditViewSetMixin, LocationScopedViewSetMixin, viewsets.ModelViewSet):
    # Continent isn't independently assignable — it's derived from whichever
    # states are in scope. "states__continent_id" is a
    # LocationScopedViewSetMixin special case: it resolves the scoped
    # States' own continent_id CharField, not a real Django relation.
    location_scope_field = "states"
    location_scope_lookup = "states__continent_id"

    queryset = Continent.objects.filter(is_deleted=False)
    serializer_class = ContinentSerializer
    lookup_field = "unique_id"
    permission_resource = "Continent"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name"]
    ordering_fields = ["name"]

    AUDIT_MODULE = "common-masters"
    AUDIT_ENDPOINT = "continents"

    def get_queryset(self):
        queryset = Continent.objects.filter(is_deleted=False)
        return self.filter_queryset_by_location_scope(queryset).distinct()
