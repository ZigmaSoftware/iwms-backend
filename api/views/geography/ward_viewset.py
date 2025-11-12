from rest_framework import viewsets
from ...apps.ward import Ward
from ...serializers.geography.ward_serializer import WardSerializer

class WardViewSet(viewsets.ModelViewSet):
    queryset = Ward.objects.all() 
    serializer_class = WardSerializer

    def get_queryset(self):
        queryset = Ward.objects.filter(is_deleted=False)
        zone_id = self.request.query_params.get("zone")
        city_id = self.request.query_params.get("city")
        district_id = self.request.query_params.get("district")
        state_id = self.request.query_params.get("state")
        country_id = self.request.query_params.get("country")
        is_active = self.request.query_params.get("is_active")

        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        elif city_id:
            queryset = queryset.filter(city_id=city_id)
        elif district_id:
            queryset = queryset.filter(district_id=district_id)
        elif state_id:
            queryset = queryset.filter(state_id=state_id)
        elif country_id:
            queryset = queryset.filter(country_id=country_id)

        if is_active is not None:
            truthy = {"1","true","True"}
            falsy = {"0","false","False"}
            if is_active in truthy:
                queryset = queryset.filter(is_active=True)
            elif is_active in falsy:
                queryset = queryset.filter(is_active=False)
        return queryset
