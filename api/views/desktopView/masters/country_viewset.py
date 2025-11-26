from rest_framework import viewsets
from api.apps.country import Country
from api.serializers.desktopView.masters.country_serializer import CountrySerializer

class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.filter(is_delete=False).order_by("name")
    serializer_class = CountrySerializer

    def perform_destroy(self, instance):
        """
        Override DELETE → soft delete only
        """
        instance.delete()
