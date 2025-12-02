from rest_framework import viewsets
from api.apps.ward import Ward
from api.serializers.desktopView.masters.ward_serializer import WardSerializer

class WardViewSet(viewsets.ModelViewSet):
    queryset = Ward.objects.filter(is_deleted=False)
    serializer_class = WardSerializer
    lookup_field = "ward_id"

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
        if city_id:
            queryset = queryset.filter(city_id=city_id)
        if district_id:
            queryset = queryset.filter(district_id=district_id)
        if state_id:
            queryset = queryset.filter(state_id=state_id)
        if country_id:
            queryset = queryset.filter(country_id=country_id)

        if is_active is not None:
            truthy = {"1","true","True"}
            falsy = {"0","false","False"}

            if is_active in truthy:
                queryset = queryset.filter(is_active=True)
            elif is_active in falsy:
                queryset = queryset.filter(is_active=False)

        return queryset
