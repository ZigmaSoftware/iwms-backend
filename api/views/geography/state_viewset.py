from rest_framework import viewsets
from ...apps.state import State
from ...serializers.geography.state_serializer import StateSerializer

class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.all() 
    serializer_class = StateSerializer

    def get_queryset(self):
        queryset = State.objects.filter(is_deleted=False)
        country_id = self.request.query_params.get("country")
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        return queryset
