from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.customers.wastecollection import WasteCollection
from app.serializers.core_modules.daily_operations.wastecollection_serializer import WasteCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)

class WasteCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = WasteCollection.objects.filter(is_deleted=False).select_related(
        "customer__ward","customer__zone","customer__city",
        "customer__district","customer__state","customer__country",
        "customer__panchayat_id",
        "customer__property_ref","customer__sub_property"
    ).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"
    filter_backends = [ModelFieldQueryFilter, ModelFieldSearchFilter, SerializerOrderingFilter]

    AUDIT_MODULE = "schedule-masters"
    AUDIT_ENDPOINT = "wastecollections"

    def get_queryset(self):
        queryset = super().get_queryset()

        mine = self.request.query_params.get("mine")
        if mine and str(mine).lower() in ("1", "true", "yes"):
            # Supervisor app waste summary: household collections on trips
            # whose plan this supervisor owns — mirrors
            # BinCollectionEventViewSet's `mine` filter (see that viewset).
            # Without this, the supervisor dashboard's Wet/Dry/Total cards
            # only ever reflected BIN collections (a separate model/table),
            # silently excluding every household collection a driver made.
            queryset = queryset.filter(
                trip_assignment_id__trip_plan_id__supervisor_id=self.request.user
            )

        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(collection_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(collection_date__lte=date_to)

        return queryset
