from rest_framework import filters, viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.masters.district import District
from app.serializers.masters.district_serializer import DistrictSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.location_scope_mixin import LocationScopedViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class DistrictViewSet(AuditViewSetMixin, LocationScopedViewSetMixin, CompanyScopedViewSet):
    location_scope_chain = [
        ("districts", "unique_id"),
        ("states", "state_id__unique_id"),
    ]

    queryset = District.objects.filter(is_deleted=False)
    serializer_class = DistrictSerializer
    lookup_field = "unique_id"
    permission_resource = "District"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="districts"

    def get_queryset(self):
        queryset = District.objects.filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)

        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)

        country_uid = self.request.query_params.get("country")
        state_uid = self.request.query_params.get("state")
        continent_uid = self.request.query_params.get("continent")

        if country_uid:
            queryset = queryset.filter(country_id__unique_id=country_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        if continent_uid:
            queryset = queryset.filter(continent_id__unique_id=continent_uid)

        return self.filter_queryset_by_location_scope(queryset)

    def perform_destroy(self, instance):
        instance.delete()
