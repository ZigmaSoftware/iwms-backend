from datetime import date

from django.db.models import Count, Sum
from rest_framework.response import Response

from app.models.collections.ward_wise_collection import WardCollection
from app.models.collections.zone_wise_collection import ZoneCollection
from app.serializers.collections.ward_wise_collection_serializer import (
    WardCollectionSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class WardWiseCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = WardCollectionSerializer
    lookup_field = "unique_id"
    permission_resource = "WardCollection"
    AUDIT_MODULE = "collections"
    AUDIT_ENDPOINT = "ward-collection"

    def get_queryset(self):
        return (
            WardCollection.objects.select_related(
                "collection_point_id",
                "bin_collection_event_id",
                "bin_collection_event_id__bin_id",
                "bin_collection_event_id__collection_point_id",
                "ward_id",
                "ward_id__zone_id",
                "waste_type_id",
                "trip_id",
                "company_id",
                "project_id",
            )
            .filter(is_deleted=False)
        )

    def _sync_zone_collection(self, instance):
        zone = getattr(instance.ward_id, "zone_id", None)
        if not zone:
            return

        filters = {
            "ward_id__zone_id": zone,
            "collection_date": instance.collection_date,
            "waste_type_id": instance.waste_type_id,
            "trip_id": instance.trip_id,
            "is_deleted": False,
        }
        aggregated = WardCollection.objects.filter(**filters).aggregate(
            total_weight=Sum("ward_total_weight"),
            ward_count=Count("unique_id"),
        )
        total_weight = aggregated["total_weight"] or 0
        ward_count = aggregated["ward_count"] or 0

        zone_filters = {
            "zone_id": zone,
            "collection_date": instance.collection_date,
            "waste_type_id": instance.waste_type_id,
            "trip_id": instance.trip_id,
        }
        if total_weight == 0:
            ZoneCollection.objects.filter(**zone_filters).delete()
            return

        ZoneCollection.objects.update_or_create(
            **zone_filters,
            defaults={
                "zone_total_weight": total_weight,
                "ward_count": ward_count,
                "company_id": instance.company_id,
                "project_id": instance.project_id,
                "is_active": True,
                "is_deleted": False,
            },
        )

    def perform_create(self, serializer):
        instance = serializer.save()
        self._sync_zone_collection(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._sync_zone_collection(instance)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        self._sync_zone_collection(instance)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        ward_id = request.query_params.get("ward_id")
        if ward_id:
            queryset = queryset.filter(ward_id=ward_id)

        date_param = request.query_params.get("date") or date.today()
        daily_total = queryset.filter(collection_date=date_param).aggregate(
            total=Sum("ward_total_weight")
        )
        overall_total = queryset.aggregate(total=Sum("ward_total_weight"))

        return Response(
            {
                "daily_total_weight": daily_total["total"] or 0,
                "overall_total_weight": overall_total["total"] or 0,
                "ward_collections": self.get_serializer(queryset, many=True).data,
            }
        )
