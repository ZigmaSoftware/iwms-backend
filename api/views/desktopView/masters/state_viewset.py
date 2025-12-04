from rest_framework import viewsets
from api.apps.state import State
from api.serializers.desktopView.masters.state_serializer import StateSerializer


class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.all()   # REQUIRED for DRF basename detection
    serializer_class = StateSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = State.objects.filter(is_deleted=False)\
            .select_related("country_id", "continent_id")\
            .order_by("name")

        country_uid = self.request.query_params.get("country")
        if country_uid:
            queryset = queryset.filter(
                country_id__unique_id=country_uid
            )

        continent_uid = self.request.query_params.get("continent")
        if continent_uid:
            queryset = queryset.filter(
                continent_id__unique_id=continent_uid
            )

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
