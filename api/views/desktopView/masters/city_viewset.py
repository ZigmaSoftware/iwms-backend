from rest_framework import viewsets
from api.apps.city import City
from api.serializers.desktopView.masters.city_serializer import CitySerializer

class CityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.filter(is_deleted=False)
    serializer_class = CitySerializer
    lookup_field = "city_id"

    def get_queryset(self):
        queryset = City.objects.filter(is_deleted=False)

        district_id = self.request.query_params.get("district")
        state_id = self.request.query_params.get("state")
        country_id = self.request.query_params.get("country")

        if district_id:
            queryset = queryset.filter(district_id=district_id)

        if state_id:
            queryset = queryset.filter(state_id=state_id)

        if country_id:
            queryset = queryset.filter(country_id=country_id)

        return queryset
