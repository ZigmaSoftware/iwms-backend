from django.db.models import Q

from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.serializers.core_modules.daily_operations.daily_trip_household_collection_serializer import (
    DailyTripHouseholdCollectionSerializer,
)
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage


class DailyTripHouseholdCollectionViewSet(CompanyScopedViewSet):
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
            from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment

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
            from app.models.customers.customercreation import CustomerCreation

            matching_customer_ids = CustomerCreation.objects.filter(
                customer_name__icontains=search,
            ).values("unique_id")
            queryset = queryset.filter(
                Q(customer_id__in=matching_customer_ids)
                | Q(trip_assignment_id__icontains=search)
            )

        return queryset
