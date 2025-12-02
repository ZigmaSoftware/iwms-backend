from rest_framework import viewsets
from api.apps.state import State
from api.serializers.desktopView.masters.state_serializer import StateSerializer

class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.filter(is_deleted=False)
    serializer_class = StateSerializer
    lookup_field = "state_id"

    def get_queryset(self):
        queryset = State.objects.filter(is_deleted=False)
        country_id = self.request.query_params.get("country")
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        return queryset
