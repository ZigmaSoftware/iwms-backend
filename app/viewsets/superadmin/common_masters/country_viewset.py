from rest_framework import filters, viewsets
from app.models.common_masters.country import Country
from app.serializers.superadmin.common_masters.country_serializer import CountrySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.location_scope_mixin import LocationScopedViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class CountryViewSet(AuditViewSetMixin, LocationScopedViewSetMixin, viewsets.ModelViewSet):
    # Country isn't independently assignable — it's derived from whichever
    # states are in scope, via State.country_id.
    location_scope_field = "states"
    location_scope_lookup = "states__unique_id"

    queryset = Country.objects.filter(is_deleted=False)
    serializer_class = CountrySerializer
    lookup_field = "unique_id"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "currency", "mob_code"]
    ordering_fields = ["name"]

    AUDIT_MODULE = "common-masters"
    AUDIT_ENDPOINT = "countries"

    def get_queryset(self):
        queryset = Country.objects.filter(is_deleted=False)

        # Filter by Continent Unique ID
        continent_uid = self.request.query_params.get("continent")
        if continent_uid:
            queryset = queryset.filter(
                continent_id__unique_id=continent_uid
            )

        return self.filter_queryset_by_location_scope(queryset).distinct()

    def perform_destroy(self, instance):
        instance.delete()  # Soft delete
