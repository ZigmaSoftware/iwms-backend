from rest_framework import viewsets
from api.apps.city import City
from api.serializers.desktopView.geography.city_serializer import CitySerializer

class CityViewSet(viewsets.ModelViewSet):
    
    queryset = City.objects.all() 
    serializer_class = CitySerializer

    def get_queryset(self):
        queryset = City.objects.filter(is_deleted=False)
        district_id = self.request.query_params.get("district")
        state_id = self.request.query_params.get("state")
        country_id = self.request.query_params.get("country")
        if district_id:
            queryset = queryset.filter(district_id=district_id)
        elif state_id:
            queryset = queryset.filter(state_id=state_id)
        elif country_id:
            queryset = queryset.filter(country_id=country_id)
        return queryset
