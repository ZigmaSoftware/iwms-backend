from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.masters.zone import Zone
from app.serializers.masters.zone_serializer import ZoneSerializer


class ZoneViewSet(CompanyScopedViewSet):
    serializer_class = ZoneSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = (
            Zone.objects
            .filter(is_deleted=False)
            .select_related(
                "continent_id",
                "country_id",
                "state_id",
                "district_id",
                "city_id",
            )
        )

        params = self.request.query_params

        filter_map = {
            "continent": "continent_id__unique_id",
            "country": "country_id__unique_id",
            "state": "state_id__unique_id",
            "district": "district_id__unique_id",
            "city": "city_id__unique_id",
        }

        for param, field in filter_map.items():
            value = params.get(param)
            if value:
                qs = qs.filter(**{field: value})

        return qs

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
