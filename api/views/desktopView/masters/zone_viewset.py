from rest_framework import viewsets
from api.apps.zone import Zone
from api.serializers.desktopView.masters.zone_serializer import ZoneSerializer

class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all() 
    serializer_class = ZoneSerializer

    def get_queryset(self):
        queryset = Zone.objects.filter(is_deleted=False)
        city_id = self.request.query_params.get("city")
        district_id = self.request.query_params.get("district")
        state_id = self.request.query_params.get("state")
        country_id = self.request.query_params.get("country")
        if city_id:
            queryset = queryset.filter(city_id=city_id)
        elif district_id:
            queryset = queryset.filter(district_id=district_id)
        elif state_id:
            queryset = queryset.filter(state_id=state_id)
        elif country_id:
            queryset = queryset.filter(country_id=country_id)
        return queryset
