from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.masters.city import City
from app.serializers.masters.city_serializer import CitySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.location_scope_mixin import LocationScopedViewSetMixin


class CityViewSet(AuditViewSetMixin, LocationScopedViewSetMixin, CompanyScopedViewSet):
    location_scope_chain = [
        ("cities", "unique_id"),
        ("districts", "district_id"),
        ("states", "state_id"),
    ]

    queryset = City.objects.filter(is_deleted=False)
    serializer_class = CitySerializer
    lookup_field = "unique_id"

    permission_resource = "City"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="cities"

    def get_queryset(self):
        queryset = City.objects.filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")

        if company_uid:
            queryset = queryset.filter(company_id=company_uid)

        if project_uid:
            queryset = queryset.filter(project_id=project_uid)

        district_uid = self.request.query_params.get("district")
        state_uid = self.request.query_params.get("state")
        country_uid = self.request.query_params.get("country")

        if district_uid:
            queryset = queryset.filter(district_id=district_uid)

        if state_uid:
            queryset = queryset.filter(state_id=state_uid)

        if country_uid:
            queryset = queryset.filter(country_id=country_uid)

        return self.filter_queryset_by_location_scope(queryset)
