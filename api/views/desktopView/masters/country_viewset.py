from rest_framework import viewsets
from api.apps.country import Country
from api.serializers.desktopView.masters.country_serializer import CountrySerializer

class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer
