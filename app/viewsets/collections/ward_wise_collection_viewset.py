# from django.db.models import Sum
# from rest_framework.response import Response
# from app.models.assets.ward_wise_collection import WardCollection
# from app.serializers.assets.ward_wise_collection_serializer import WardCollectionSerializer
# from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
# from datetime import date
# from app.utils.audit_mixin import AuditViewSetMixin


# class WardWiseCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):

#     serializer_class = WardCollectionSerializer
#     lookup_field = "unique_id"

#     AUDIT_MODULE = "bp-palakkad"
#     AUDIT_ENDPOINT = "ward-collection"

#     def get_queryset(self):
#         return WardCollection.objects.select_related(
#             "point_collection_id",
#             "point_collection_id__bin_id",           
#             "point_collection_id__collection_point_id",  
#             "ward_id",
#             "waste_type_id",
#             "trip_id",
#             "company_id",
#             "project_id"
#         ).filter(is_deleted=False)

#     def list(self, request, *args, **kwargs):

#         queryset = self.filter_queryset(self.get_queryset())

#         ward_id = request.query_params.get("ward_id")
#         if ward_id:
#             queryset = queryset.filter(ward_id=ward_id)

#         serializer = self.get_serializer(queryset, many=True)

#         date_param = request.query_params.get("date") or date.today()

#         daily_total = queryset.filter(
#             collection_date=date_param
#         ).aggregate(total=Sum("ward_total_weight"))

#         overall_total = queryset.aggregate(
#             total=Sum("ward_total_weight")
#         )

#         return Response({
#             "daily_total_weight": daily_total["total"] or 0,
#             "overall_total_weight": overall_total["total"] or 0,
#             "ward_collections": serializer.data
#         })




from django.db.models import Sum, Count
from rest_framework.response import Response
from app.models.collections.ward_wise_collection import WardCollection
from app.models.collections.zone_wise_collection import ZoneCollection
from app.serializers.collections.ward_wise_collection_serializer import WardCollectionSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from datetime import date
from app.utils.audit_mixin import AuditViewSetMixin


class WardWiseCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):

    serializer_class = WardCollectionSerializer
    lookup_field = "unique_id"

    permission_resource = "WardCollection"

    AUDIT_MODULE = "collections"
    AUDIT_ENDPOINT = "ward-collection"

    def get_queryset(self):
        return WardCollection.objects.select_related(
            "point_collection_id",
            "point_collection_id__collection_point_id",
            "ward_id",
            "ward_id__zone_id",
            "waste_type_id",
            "trip_id",
            "company_id",
            "project_id"
        ).filter(is_deleted=False)

    # ------------------------------------------------------------------ #
    #  Zone sync helper — called after every create / update / destroy    #
    # ------------------------------------------------------------------ #
    def _sync_zone_collection(self, instance):
        """
        Re-aggregates all WardCollections for the same
        zone + date + waste_type + trip and upserts ZoneCollection.
        """
        ward = instance.ward_id
        zone = getattr(ward, "zone_id", None)

        if zone is None:
            return  # Ward has no zone assigned — nothing to sync

        collection_date = instance.collection_date
        waste_type     = instance.waste_type_id
        trip           = instance.trip_id
        company        = instance.company_id
        project        = instance.project_id

        aggregated = WardCollection.objects.filter(
            ward_id__zone_id=zone,
            collection_date=collection_date,
            waste_type_id=waste_type,
            trip_id=trip,
            is_deleted=False,
        ).aggregate(
            total_weight=Sum("ward_total_weight"),
            ward_count=Count("id")
        )

        total_weight = aggregated["total_weight"] or 0
        ward_count   = aggregated["ward_count"]   or 0

        if total_weight == 0:
            # No active ward data remains — remove the zone record
            ZoneCollection.objects.filter(
                zone_id=zone,
                collection_date=collection_date,
                waste_type_id=waste_type,
                trip_id=trip,
            ).delete()
            return

        ZoneCollection.objects.update_or_create(
            zone_id=zone,
            collection_date=collection_date,
            waste_type_id=waste_type,
            trip_id=trip,
            defaults={
                "zone_total_weight": total_weight,
                "ward_count":        ward_count,
                "company_id":        company,
                "project_id":        project,
                "is_deleted":        False,
            }
        )

    # ------------------------------------------------------------------ #
    #  CRUD overrides                                                      #
    # ------------------------------------------------------------------ #
    def perform_create(self, serializer):
        instance = serializer.save()
        self._sync_zone_collection(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._sync_zone_collection(instance)

    def perform_destroy(self, instance):
        instance.is_deleted = True
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

        serializer = self.get_serializer(queryset, many=True)

        date_param = request.query_params.get("date") or date.today()

        daily_total = queryset.filter(
            collection_date=date_param
        ).aggregate(total=Sum("ward_total_weight"))

        overall_total = queryset.aggregate(
            total=Sum("ward_total_weight")
        )

        return Response({
            "daily_total_weight":   daily_total["total"]   or 0,
            "overall_total_weight": overall_total["total"] or 0,
            "ward_collections":     serializer.data
        })