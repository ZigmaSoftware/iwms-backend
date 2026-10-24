from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.serializers.core_modules.daily_operations.daily_trip_household_collection_serializer import (
    DailyTripHouseholdCollectionSerializer,
)
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage
from app.utils.bulk_upload_mixin import BulkUploadMixin


class DailyTripHouseholdCollectionViewSet(BulkUploadMixin, CompanyScopedViewSet):
    serializer_class = DailyTripHouseholdCollectionSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripHouseholdCollection"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["sequence", "status", "collected_at"]

    def get_queryset(self):
        queryset = DailyTripHouseholdCollection.objects.filter(is_deleted=False)

        params = self.request.query_params
        assignment = params.get("trip_assignment_id")
        customer = params.get("customer_id")
        company = params.get("company_id")
        project = params.get("project_id")
        status_value = params.get("status")
        collection_type = params.get("collection_type")
        is_collected = params.get("is_collected")
        trip_date = params.get("date") or params.get("trip_date")
        panchayat = params.get("panchayat_id")
        ward = params.get("ward_id")
        zone = params.get("zone_id")
        search = params.get("search")

        if company:
            queryset = queryset.filter(company_id=company)
        if project:
            queryset = queryset.filter(project_id=project)
        if assignment:
            queryset = queryset.filter(trip_assignment_id=assignment)
        if customer:
            queryset = queryset.filter(customer_id=customer)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if collection_type:
            queryset = queryset.filter(collection_type=collection_type)
        if is_collected is not None:
            queryset = queryset.filter(
                is_collected=str(is_collected).lower() in {"1", "true", "yes"}
            )
        if trip_date:
            from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment

            assignment_ids = DailyTripAssignment.objects.filter(
                trip_date=trip_date,
            ).values("unique_id")
            queryset = queryset.filter(trip_assignment_id__in=assignment_ids)
        if panchayat:
            queryset = queryset.filter(panchayat_id=panchayat)
        if ward:
            queryset = queryset.filter(ward_id=ward)
        if zone:
            queryset = queryset.filter(zone_id=zone)
        if search:
            from app.models.masters.customer_masters.customercreation import CustomerCreation

            matching_customer_ids = CustomerCreation.objects.filter(
                customer_name__icontains=search,
            ).values("unique_id")
            queryset = queryset.filter(
                Q(customer_id__in=matching_customer_ids)
                | Q(trip_assignment_id__icontains=search)
            )

        return queryset

    # GET .../daily-trip-household-collections/summary/
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """Overall and today's collected weight over every row matching the
        list's own filters, not just the page on screen."""
        qs = (
            self.filter_queryset(self.get_queryset())
            .filter(collected_weight_kg__isnull=False)
            .order_by()
        )
        overall = qs.aggregate(weight=Sum("collected_weight_kg"), count=Count("pk"))
        today = qs.filter(collected_at__date=timezone.localdate()).aggregate(
            weight=Sum("collected_weight_kg"), count=Count("pk")
        )
        return Response({
            "total_weight_kg": round(float(overall["weight"] or 0), 2),
            "total_count": overall["count"],
            "today_weight_kg": round(float(today["weight"] or 0), 2),
            "today_count": today["count"],
        })
