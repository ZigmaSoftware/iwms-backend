# from django.db.models import Sum
# from rest_framework.response import Response
# from app.models.assets.panchayat_wise_collection import PanchayatCollection
# from app.serializers.assets.panchayat_wise_collection_serializer import PanchayatCollectionSerializer
# from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
# from datetime import date
# from app.utils.audit_mixin import AuditViewSetMixin


# class PanchayatWiseCollectionViewSet(AuditViewSetMixin,CompanyScopedViewSet):

#     serializer_class = PanchayatCollectionSerializer
#     lookup_field = "unique_id"

#     AUDIT_MODULE = "bp-palakkad"
#     AUDIT_ENDPOINT ="panchayat-collection"

    
#     def get_queryset(self):
#         return PanchayatCollection.objects.filter(is_deleted=False)

#     def list(self, request, *args, **kwargs):

#         queryset = self.filter_queryset(self.get_queryset())

#         panchayat_id = request.query_params.get("panchayat_id")
#         if panchayat_id:
#             queryset = queryset.filter(panchayat_id=panchayat_id)

#         serializer = self.get_serializer(queryset, many=True)

#         date_param = request.query_params.get("date") or date.today()

#         daily_total = {"total": 0}
#         if date_param:
#             daily_total = queryset.filter(
#                 collection_date=date_param
#             ).aggregate(
#                 total=Sum("panchayat_total_weight")
#             )

#         overall_total = queryset.aggregate(
#             total=Sum("panchayat_total_weight")
#         )

#         return Response({
#             "daily_total_weight": daily_total["total"] if daily_total else None,
#             "overall_total_weight": overall_total["total"] or 0,
#             "panchayat_collections": serializer.data
#         })



from django.db.models import Sum
from rest_framework.response import Response
from app.models.collections.panchayat_wise_collection import PanchayatCollection
from app.serializers.collections.panchayat_wise_collection_serializer import PanchayatCollectionSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from datetime import date
from app.utils.audit_mixin import AuditViewSetMixin


class PanchayatWiseCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):

    serializer_class = PanchayatCollectionSerializer
    lookup_field = "unique_id"

    permission_resource = "PanchayatCollection"

    AUDIT_MODULE = "collections"
    AUDIT_ENDPOINT = "panchayat-collection"

    def get_queryset(self):
        return PanchayatCollection.objects.select_related(
            "point_collection_id",
            "point_collection_id__collection_point_id",       
            "bin_collection_event_id",
            "bin_collection_event_id__bin_id",
            "bin_collection_event_id__collection_point_id",
            "panchayat_id",
            "waste_type_id",
            "trip_id",
            "company_id",
            "project_id"
        ).filter(is_deleted=False)

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(self.get_queryset())

        panchayat_id = request.query_params.get("panchayat_id")
        if panchayat_id:
            queryset = queryset.filter(panchayat_id=panchayat_id)

        serializer = self.get_serializer(queryset, many=True)

        date_param = request.query_params.get("date") or date.today()

        daily_total = queryset.filter(
            collection_date=date_param
        ).aggregate(total=Sum("panchayat_total_weight"))

        overall_total = queryset.aggregate(
            total=Sum("panchayat_total_weight")
        )

        return Response({
            "daily_total_weight": daily_total["total"] or 0,
            "overall_total_weight": overall_total["total"] or 0,
            "panchayat_collections": serializer.data
        })
