from rest_framework import viewsets
from api.apps.district import District
from api.serializers.desktopView.masters.district_serializer import DistrictSerializer

class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.all() 
    serializer_class = DistrictSerializer

    def get_queryset(self):
        queryset = District.objects.filter(is_deleted=False)
        state_id = self.request.query_params.get("state")
        if state_id:
            queryset = queryset.filter(state_id=state_id)
        return queryset
