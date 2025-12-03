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
        continent_uid = self.request.query_params.get("continent")

        if city_uid:
            queryset = queryset.filter(city_id__unique_id=city_uid)

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        if country_uid:
            queryset = queryset.filter(country_id__unique_id=country_uid)

        if continent_uid:
            queryset = queryset.filter(continent_id__unique_id=continent_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
