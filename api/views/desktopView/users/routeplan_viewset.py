from rest_framework import viewsets
from api.apps.routeplan import RoutePlan
from api.serializers.desktopView.users.routeplan_serializer import (
    RoutePlanSerializer
)


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

        params = self.request.query_params

        if params.get("district_id"):
            qs = qs.filter(district_id=params["district_id"])

        if params.get("city_id"):
            qs = qs.filter(city_id=params["city_id"])

        if params.get("zone_id"):
            qs = qs.filter(zone_id=params["zone_id"])

        if params.get("vehicle_id"):
            qs = qs.filter(vehicle_id=params["vehicle_id"])

        if params.get("supervisor_id"):
            qs = qs.filter(supervisor_id=params["supervisor_id"])

        if params.get("is_active"):
            qs = qs.filter(status=params["is_active"])

        return qs
