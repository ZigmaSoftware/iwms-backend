from rest_framework import viewsets
from api.viewsets.superadminmasters.tenant_viewset import TenantModelViewSet
from api.models.commonmasters.country import Country
from api.serializers.desktop.commonmasters.country_serializer import CountrySerializer

class CountryViewSet(TenantModelViewSet):
    queryset = Country.objects.filter(is_deleted=False)
    serializer_class = CountrySerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = Country.objects.filter(is_deleted=False)

        # Filter by Continent Unique ID
        continent_uid = self.request.query_params.get("continent")
        if continent_uid:
            queryset = queryset.filter(
                continent_id__unique_id=continent_uid
            )
            
        return queryset

    def perform_destroy(self, instance):
        instance.delete()  # Soft delete
