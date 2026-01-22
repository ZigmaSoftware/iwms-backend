from rest_framework import viewsets
from api.apps.routeplan import RoutePlan
from api.serializers.desktopView.users.routeplan_serializer import RoutePlanSerializer


class RoutePlanViewSet(viewsets.ModelViewSet):
    """
    Route Plan CRUD
    """

    serializer_class = RoutePlanSerializer
    lookup_field = "unique_id"
    permission_resource = "RoutePlan"

    def get_queryset(self):
        qs = RoutePlan.objects.select_related(
            "district_id",
            "city_id",
            "zone_id",
            "vehicle_id",
            "supervisor_id",
            "supervisor_id__staff_id",
            "supervisor_id__staffusertype_id",
        ).filter(is_deleted=False)

        district_id = self.request.query_params.get("district_id")
        city_id = self.request.query_params.get("city_id")
        zone_id = self.request.query_params.get("zone_id")
        vehicle_id = self.request.query_params.get("vehicle_id")
        supervisor_id = self.request.query_params.get("supervisor_id")
        status = self.request.query_params.get("status")

        if district_id:
            qs = qs.filter(district_id=district_id)

        if city_id:
            qs = qs.filter(city_id=city_id)

        if zone_id:
            qs = qs.filter(zone_id=zone_id)

        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)

        if supervisor_id:
            qs = qs.filter(supervisor_id=supervisor_id)

        if status:
            qs = qs.filter(status=status)

        return qs
