from rest_framework import viewsets
from api.apps.ward import Ward
from api.serializers.desktopView.masters.ward_serializer import WardSerializer


class WardViewSet(viewsets.ModelViewSet):
    queryset = Ward.objects.filter(is_deleted=False)
    serializer_class = WardSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = Ward.objects.filter(is_deleted=False)

        zone_uid = self.request.query_params.get("zone")
        city_uid = self.request.query_params.get("city")
        district_uid = self.request.query_params.get("district")
        state_uid = self.request.query_params.get("state")
        country_uid = self.request.query_params.get("country")
        is_active = self.request.query_params.get("is_active")

        if zone_uid:
            queryset = queryset.filter(zone__unique_id=zone_uid)

        if city_uid:
            queryset = queryset.filter(city__unique_id=city_uid)

        if district_uid:
            queryset = queryset.filter(district__unique_id=district_uid)

        if state_uid:
            queryset = queryset.filter(state__unique_id=state_uid)

        if country_uid:
            queryset = queryset.filter(country__unique_id=country_uid)

        if is_active is not None:
            truthy = {"1", "true", "True"}
            falsy = {"0", "false", "False"}

            if is_active in truthy:
                queryset = queryset.filter(is_active=True)
            elif is_active in falsy:
                queryset = queryset.filter(is_active=False)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
