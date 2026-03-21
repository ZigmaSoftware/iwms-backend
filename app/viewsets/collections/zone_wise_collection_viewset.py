# ──────────────────────────────────────────────────────────────────────────────
# app/viewsets/assets/ward_wise_collection_viewset.py
# ──────────────────────────────────────────────────────────────────────────────
from django.db.models import Sum, Count
from rest_framework.response import Response
from datetime import date

from app.models.collections.ward_wise_collection import WardCollection
from app.models.collections.zone_wise_collection import ZoneCollection
from app.serializers.collections.ward_wise_collection_serializer import WardCollectionSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class WardWiseCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):

    serializer_class = WardCollectionSerializer
    lookup_field = "unique_id"


    permission_resource = "WardCollection"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT = "ward-collection"

    def get_queryset(self):
        return WardCollection.objects.select_related(
            "point_collection_id",
            "point_collection_id__bin_id",
            "point_collection_id__collection_point_id",
            "ward_id",
            "ward_id__zone_id",        # needed for zone sync
            "waste_type_id",
            "trip_id",
            "company_id",
            "project_id"
        ).filter(is_deleted=False)

    # ------------------------------------------------------------------ #
    #  Zone sync                                                           #
    # ------------------------------------------------------------------ #
    def _sync_zone_collection(self, instance):
        """
        After any ward collection change, re-aggregate the matching
        ZoneCollection row (zone + date + waste_type + trip).
        """
        ward = instance.ward_id
        zone = getattr(ward, "zone_id", None)

        if zone is None:
            return  # ward has no zone — skip

        filters = dict(
            ward_id__zone_id=zone,
            collection_date=instance.collection_date,
            waste_type_id=instance.waste_type_id,
            trip_id=instance.trip_id,
            is_deleted=False,
        )

        aggregated = WardCollection.objects.filter(**filters).aggregate(
            total_weight=Sum("ward_total_weight"),
            ward_count=Count("id")
        )

        total_weight = aggregated["total_weight"] or 0
        ward_count   = aggregated["ward_count"]   or 0

        zone_filters = dict(
            zone_id=zone,
            collection_date=instance.collection_date,
            waste_type_id=instance.waste_type_id,
            trip_id=instance.trip_id,
        )

        if total_weight == 0:
            # All wards for this zone removed — clean up the zone record
            ZoneCollection.objects.filter(**zone_filters).delete()
            return

        ZoneCollection.objects.update_or_create(
            **zone_filters,
            defaults={
                "zone_total_weight": total_weight,
                "ward_count":        ward_count,
                "company_id":        instance.company_id,
                "project_id":        instance.project_id,
                "is_active":         True,
                "is_deleted":        False,
            }
        )

    # ------------------------------------------------------------------ #
    #  CRUD hooks                                                          #
    # ------------------------------------------------------------------ #
    def perform_create(self, serializer):
        instance = serializer.save()
        self._sync_zone_collection(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._sync_zone_collection(instance)

    def perform_destroy(self, instance):
        """Soft-delete, then re-sync zone totals."""
        instance.is_deleted = True
        instance.is_active  = False
        instance.save()
        self._sync_zone_collection(instance)

    # ------------------------------------------------------------------ #
    #  List                                                                #
    # ------------------------------------------------------------------ #
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        ward_id = request.query_params.get("ward_id")
        if ward_id:
            queryset = queryset.filter(ward_id=ward_id)

        serializer  = self.get_serializer(queryset, many=True)
        date_param  = request.query_params.get("date") or date.today()

        daily_total   = queryset.filter(collection_date=date_param).aggregate(total=Sum("ward_total_weight"))
        overall_total = queryset.aggregate(total=Sum("ward_total_weight"))

        return Response({
            "daily_total_weight":   daily_total["total"]   or 0,
            "overall_total_weight": overall_total["total"] or 0,
            "ward_collections":     serializer.data,
        })


# ──────────────────────────────────────────────────────────────────────────────
# app/viewsets/assets/zone_wise_collection_viewset.py
# ──────────────────────────────────────────────────────────────────────────────
from app.models.collections.zone_wise_collection import ZoneCollection
from app.serializers.collections.zone_wise_collection_serializer import ZoneCollectionSerializer


class ZoneWiseCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):

    serializer_class = ZoneCollectionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT = "zone-collection"

    def get_queryset(self):
        return ZoneCollection.objects.select_related(
            "zone_id",
            "waste_type_id",
            "trip_id",
            "company_id",
            "project_id"
        ).filter(is_deleted=False)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        zone_id = request.query_params.get("zone_id")
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)

        serializer  = self.get_serializer(queryset, many=True)
        date_param  = request.query_params.get("date") or date.today()

        daily_total   = queryset.filter(collection_date=date_param).aggregate(total=Sum("zone_total_weight"))
        overall_total = queryset.aggregate(total=Sum("zone_total_weight"))

        return Response({
            "daily_total_weight":   daily_total["total"]   or 0,
            "overall_total_weight": overall_total["total"] or 0,
            "zone_collections":     serializer.data,
        })