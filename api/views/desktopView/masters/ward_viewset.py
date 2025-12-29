from rest_framework import viewsets
from api.apps.ward import Ward
from api.serializers.desktopView.masters.ward_serializer import WardSerializer


class WardViewSet(viewsets.ModelViewSet):
    serializer_class = WardSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = (
            Ward.objects
            .filter(is_deleted=False)
            .select_related(
                "continent_id",
                "country_id",
                "state_id",
                "district_id",
                "city_id",
                "zone_id",
            )
        )

        params = self.request.query_params

        filter_map = {
            "continent": "continent_id__unique_id",
            "country": "country_id__unique_id",
            "state": "state_id__unique_id",
            "district": "district_id__unique_id",
            "city": "city_id__unique_id",
            "zone": "zone_id__unique_id",
        }

        for param, field in filter_map.items():
            value = params.get(param)
            if value:
                qs = qs.filter(**{field: value})

        is_active = params.get("is_active")
        if is_active is not None:
            is_active = is_active.lower()
            if is_active in ("1", "true", "yes"):
                qs = qs.filter(is_active=True)
            elif is_active in ("0", "false", "no"):
                qs = qs.filter(is_active=False)

        return qs

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
