from rest_framework import viewsets
from api.apps.city import City
from api.serializers.desktopView.masters.city_serializer import CitySerializer


class CityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.filter(is_deleted=False)
    serializer_class = CitySerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = City.objects.filter(is_deleted=False)

        district_uid = self.request.query_params.get("district")
        state_uid = self.request.query_params.get("state")
        country_uid = self.request.query_params.get("country")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        if country_uid:
            queryset = queryset.filter(country_id__unique_id=country_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
