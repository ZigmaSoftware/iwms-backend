from rest_framework import viewsets
from api.apps.country import Country
from api.serializers.desktopView.masters.country_serializer import CountrySerializer

class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.filter(is_deleted=False)
    serializer_class = CountrySerializer
    lookup_field = "country_id"

    def get_queryset(self):
        queryset = Country.objects.filter(is_deleted=False)

        # Filter by continent
        continent_id = self.request.query_params.get("continent")
        if continent_id:
            queryset = queryset.filter(continent_id=continent_id)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()     # Soft delete only
