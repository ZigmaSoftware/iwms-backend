from datetime import date

from django.db.models import Sum
from rest_framework.response import Response

from app.models.collections.zone_wise_collection import ZoneCollection
from app.serializers.collections.zone_wise_collection_serializer import ZoneCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class ZoneWiseCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = ZoneCollectionSerializer
    lookup_field = "unique_id"
    permission_resource = "ZoneCollection"
    AUDIT_MODULE = "collections"
    AUDIT_ENDPOINT = "zone-collection"

    def get_queryset(self):
        return (
            ZoneCollection.objects.select_related(
                "zone_id",
                "waste_type_id",
                "trip_id",
                "company_id",
                "project_id",
            )
            .filter(is_deleted=False)
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        zone_id = request.query_params.get("zone_id")
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)

        date_param = request.query_params.get("date") or date.today()
        daily_total = queryset.filter(collection_date=date_param).aggregate(
            total=Sum("zone_total_weight")
        )
        overall_total = queryset.aggregate(total=Sum("zone_total_weight"))

        return Response(
            {
                "daily_total_weight": daily_total["total"] or 0,
                "overall_total_weight": overall_total["total"] or 0,
                "zone_collections": self.get_serializer(queryset, many=True).data,
            }
        )
