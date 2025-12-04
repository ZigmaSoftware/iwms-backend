from rest_framework import viewsets
from api.apps.district import District
from api.serializers.desktopView.masters.district_serializer import DistrictSerializer

class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.filter(is_deleted=False)
    serializer_class = DistrictSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = District.objects.filter(is_deleted=False)

        country_uid = self.request.query_params.get("country")
        state_uid = self.request.query_params.get("state")
        continent_uid = self.request.query_params.get("continent")

        if country_uid:
            queryset = queryset.filter(country_id__unique_id=country_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        if continent_uid:
            queryset = queryset.filter(continent_id__unique_id=continent_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
