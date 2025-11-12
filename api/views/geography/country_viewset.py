from rest_framework import viewsets
from ...apps.country import Country
from ...serializers.geography.country_serializer import CountrySerializer

class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer
