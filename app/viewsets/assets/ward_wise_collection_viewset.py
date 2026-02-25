from django.db.models import Sum
from rest_framework.response import Response
from app.models.assets.ward_wise_collection import WardCollection
from app.serializers.assets.ward_wise_collection_serializer import WardCollectionSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from datetime import date
from app.utils.audit_mixin import AuditViewSetMixin


class WardWiseCollectionViewSet(AuditViewSetMixin,CompanyScopedViewSet):

    serializer_class = WardCollectionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="ward-collection"

    def get_queryset(self):
        return WardCollection.objects.filter(is_deleted=False)

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(self.get_queryset())

        ward_id = request.query_params.get("ward_id")
        if ward_id:
            queryset = queryset.filter(ward_id=ward_id)

        serializer = self.get_serializer(queryset, many=True)

        date_param = request.query_params.get("date") or date.today()

        daily_total = {"total": 0}
        if date_param:
            daily_total = queryset.filter(
                collection_date=date_param
            ).aggregate(
                total=Sum("ward_total_weight")
            )

        overall_total = queryset.aggregate(
            total=Sum("ward_total_weight")
        )

        return Response({
            "daily_total_weight": daily_total["total"] if daily_total else None,
            "overall_total_weight": overall_total["total"] or 0,
            "ward_collections": serializer.data
        })