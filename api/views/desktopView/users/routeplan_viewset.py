from rest_framework import viewsets

from api.apps.routeplan import RoutePlan
from api.serializers.desktopView.users.routeplan_serializer import RoutePlanSerializer


class RoutePlanViewSet(viewsets.ModelViewSet):
    """
    Route Plan CRUD
    """

    queryset = RoutePlan.objects.all()
    serializer_class = RoutePlanSerializer
    lookup_field = "unique_id"
    # 🔒 REQUIRED if you are using ModulePermissionMiddleware
    permission_resource = "RoutePlan"

    def get_queryset(self):
        qs = super().get_queryset()

        district_id = self.request.query_params.get("district_id")
        city_id = self.request.query_params.get("city_id")
        vehicle_id = self.request.query_params.get("vehicle_id")
        supervisor_id = self.request.query_params.get("supervisor_id")
        status = self.request.query_params.get("status")

        if district_id:
            qs = qs.filter(district_id=district_id)

        if city_id:
            qs = qs.filter(city_id=city_id)

        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)

        if supervisor_id:
            qs = qs.filter(supervisor_id=supervisor_id)

        if status:
            qs = qs.filter(status=status)

        return qs
