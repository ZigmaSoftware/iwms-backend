from rest_framework import viewsets
from api.apps.country import Country
from api.serializers.desktopView.masters.country_serializer import CountrySerializer

class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.filter(is_delete=False)
    serializer_class = CountrySerializer
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
