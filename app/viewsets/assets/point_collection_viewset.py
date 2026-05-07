# 



from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, Count
from datetime import date

from app.models.assets.point_collection import PointCollection
from app.serializers.assets.point_collection_serializer import PointCollectionSerializer
from app.models.collections.panchayat_wise_collection import PanchayatCollection
from app.models.collections.ward_wise_collection import WardCollection
from app.models.collections.zone_wise_collection import ZoneCollection

from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class PointCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):

    serializer_class = PointCollectionSerializer
    lookup_field = "unique_id"

    permission_resource = "PointCollection"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT = "point-collection"

    # -------------------------------------------------
    # QUERYSET
    # -------------------------------------------------

    def get_queryset(self):
        queryset = PointCollection.objects.select_related(
            "collection_point_id",
            "collection_point_id__panchayat_id",
            "collection_point_id__ward_id",
            "collection_point_id__ward_id__zone_id",   
            "district_id",
            "city_id",
            "waste_type_id",
            "trip_id",
            "company_id",
            "project_id"
        ).filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        city_uid = self.request.query_params.get("city") or self.request.query_params.get("city_id")
        panchayat_uid = self.request.query_params.get("panchayat") or self.request.query_params.get("panchayat_id")
        ward_uid = self.request.query_params.get("ward") or self.request.query_params.get("ward_id")
        zone_uid = self.request.query_params.get("zone") or self.request.query_params.get("zone_id")
        collection_point_uid = (
            self.request.query_params.get("collection_point")
            or self.request.query_params.get("collection_point_id")
        )
        bin_uid = self.request.query_params.get("bin") or self.request.query_params.get("bin_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)

        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if city_uid:
            queryset = queryset.filter(city_id__unique_id=city_uid)

        if panchayat_uid:
            queryset = queryset.filter(collection_point_id__panchayat_id__unique_id=panchayat_uid)

        if ward_uid:
            queryset = queryset.filter(collection_point_id__ward_id__unique_id=ward_uid)

        if zone_uid:
            queryset = queryset.filter(collection_point_id__ward_id__zone_id__unique_id=zone_uid)

        if collection_point_uid:
            queryset = queryset.filter(collection_point_id__unique_id=collection_point_uid)

        if bin_uid:
            queryset = queryset.filter(bin_id__unique_id=bin_uid)

        return queryset

    # -------------------------------------------------
    # SOFT DELETE
    # -------------------------------------------------

    def perform_destroy(self, instance):

        ward = instance.collection_point_id.ward_id

        PanchayatCollection.objects.filter(
            point_collection_id=instance
        ).update(is_deleted=True)

        WardCollection.objects.filter(
            point_collection_id=instance
        ).update(is_deleted=True)

        instance.is_deleted = True
        instance.save()

        # Re-sync zone after ward collections are soft-deleted
        if ward:
            self._sync_zone_collection(instance, ward)

    # -------------------------------------------------
    # HELPERS
    # -------------------------------------------------

    def _sync_panchayat_collection(self, instance, panchayat):
        """
        Creates a 1:1 PanchayatCollection row if one doesn't exist yet.
        If it already exists, syncs weight and date.
        Also self-heals legacy aggregate rows (point_collection_id=null).
        """
        updated = PanchayatCollection.objects.filter(
            point_collection_id=instance
        ).update(
            collection_date=instance.collection_date,
            panchayat_total_weight=instance.point_collection_weight,
            updated_by=self.request.user.account
        )

        if updated == 0:
            PanchayatCollection.objects.filter(
                panchayat_id=panchayat,
                waste_type_id=instance.waste_type_id,
                collection_date=instance.collection_date,
                trip_id=instance.trip_id,
                point_collection_id__isnull=True
            ).delete()

            PanchayatCollection.objects.create(
                point_collection_id=instance,
                panchayat_id=panchayat,
                waste_type_id=instance.waste_type_id,
                collection_date=instance.collection_date,
                trip_id=instance.trip_id,
                company_id=instance.company_id,
                project_id=instance.project_id,
                panchayat_total_weight=instance.point_collection_weight,
                created_by=self.request.user.account,
                updated_by=self.request.user.account
            )

    def _sync_ward_collection(self, instance, ward):
        """
        Creates a 1:1 WardCollection row if one doesn't exist yet.
        If it already exists, syncs weight and date.
        Also self-heals legacy aggregate rows (point_collection_id=null).
        """
        updated = WardCollection.objects.filter(
            point_collection_id=instance
        ).update(
            collection_date=instance.collection_date,
            ward_total_weight=instance.point_collection_weight,
            updated_by=self.request.user.account
        )

        if updated == 0:
            WardCollection.objects.filter(
                ward_id=ward,
                waste_type_id=instance.waste_type_id,
                collection_date=instance.collection_date,
                trip_id=instance.trip_id,
                point_collection_id__isnull=True
            ).delete()

            WardCollection.objects.create(
                point_collection_id=instance,
                ward_id=ward,
                waste_type_id=instance.waste_type_id,
                collection_date=instance.collection_date,
                trip_id=instance.trip_id,
                company_id=instance.company_id,
                project_id=instance.project_id,
                ward_total_weight=instance.point_collection_weight,
                created_by=self.request.user.account,
                updated_by=self.request.user.account
            )

    def _sync_zone_collection(self, instance, ward):
        """
        Re-aggregates all active WardCollections for the same
        zone + date + waste_type + trip and upserts one ZoneCollection row.
        Called after every ward sync (create, update, soft-delete).
        """
        zone = getattr(ward, "zone_id", None)

        if zone is None:
            return  # ward has no zone assigned — skip

        # Sum all active ward collections under this zone for the same trip/date/waste
        aggregated = WardCollection.objects.filter(
            ward_id__zone_id=zone,
            collection_date=instance.collection_date,
            waste_type_id=instance.waste_type_id,
            trip_id=instance.trip_id,
            is_deleted=False,
        ).aggregate(
            total_weight=Sum("ward_total_weight"),
            ward_count=Count("unique_id")
        )

        total_weight = aggregated["total_weight"] or 0
        ward_count   = aggregated["ward_count"]   or 0

        zone_lookup = dict(
            zone_id=zone,
            collection_date=instance.collection_date,
            waste_type_id=instance.waste_type_id,
            trip_id=instance.trip_id,
        )

        if total_weight == 0:
            # No active ward data left for this zone — remove zone record
            ZoneCollection.objects.filter(**zone_lookup).delete()
            return

        ZoneCollection.objects.update_or_create(
            **zone_lookup,
            defaults={
                "zone_total_weight": total_weight,
                "ward_count":        ward_count,
                "company_id":        instance.company_id,
                "project_id":        instance.project_id,
                "is_active":         True,
                "is_deleted":        False,
            }
        )

    # -------------------------------------------------
    # CREATE
    # -------------------------------------------------

    @transaction.atomic
    def perform_create(self, serializer):

        super().perform_create(serializer)

        instance = serializer.instance

        if not instance.is_collected:
            return

        panchayat = instance.collection_point_id.panchayat_id
        ward      = instance.collection_point_id.ward_id

        if panchayat:
            self._sync_panchayat_collection(instance, panchayat)

        if ward:
            self._sync_ward_collection(instance, ward)
            self._sync_zone_collection(instance, ward)   # ← auto-create zone record

    # -------------------------------------------------
    # UPDATE
    # -------------------------------------------------

    @transaction.atomic
    def perform_update(self, serializer):

        instance = serializer.save(updated_by=self.request.user.account)

        panchayat = instance.collection_point_id.panchayat_id
        ward      = instance.collection_point_id.ward_id

        if panchayat:
            if instance.is_collected:
                self._sync_panchayat_collection(instance, panchayat)
            else:
                PanchayatCollection.objects.filter(
                    point_collection_id=instance
                ).update(is_deleted=True)

        if ward:
            if instance.is_collected:
                self._sync_ward_collection(instance, ward)
                self._sync_zone_collection(instance, ward)   # ← re-sync zone on update
            else:
                WardCollection.objects.filter(
                    point_collection_id=instance
                ).update(is_deleted=True)
                self._sync_zone_collection(instance, ward)   # ← re-sync zone on uncollect

    # -------------------------------------------------
    # LIST WITH TOTALS
    # -------------------------------------------------

    def list(self, request, *args, **kwargs):

        queryset = self.get_queryset()

        collection_point_id = request.query_params.get("collection_point_id")
        if collection_point_id:
            queryset = queryset.filter(collection_point_id=collection_point_id)

        serializer = self.get_serializer(queryset, many=True)

        today = date.today()

        daily_total = queryset.filter(
            collection_date=today
        ).aggregate(total=Sum("point_collection_weight"))

        overall_total = queryset.aggregate(
            total=Sum("point_collection_weight")
        )

        return Response({
            "date": today,
            "daily_total_weight": daily_total["total"] or 0,
            "overall_total_weight": overall_total["total"] or 0,
            "collections": serializer.data
        })
