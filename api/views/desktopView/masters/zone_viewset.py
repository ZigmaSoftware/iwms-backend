from rest_framework import viewsets
from api.apps.zone import Zone
from api.serializers.desktopView.masters.zone_serializer import ZoneSerializer


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.filter(is_deleted=False)
    serializer_class = ZoneSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = Zone.objects.filter(is_deleted=False)

        city_uid = self.request.query_params.get("city")
        district_uid = self.request.query_params.get("district")
        state_uid = self.request.query_params.get("state")
        country_uid = self.request.query_params.get("country")

        if city_uid:
            queryset = queryset.filter(city__unique_id=city_uid)

        if district_uid:
            queryset = queryset.filter(district__unique_id=district_uid)

        if state_uid:
            queryset = queryset.filter(state__unique_id=state_uid)

        if country_uid:
            queryset = queryset.filter(country__unique_id=country_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
