from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.customers.wastecollection import WasteCollection
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.trip_plan import TripPlan
from app.serializers.core_modules.daily_operations.wastecollection_serializer import WasteCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)

class WasteCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    # `customer`/`ward` are no longer real FKs (converted to plain CharFields),
    # so there is nothing left here for select_related to traverse.
    queryset = WasteCollection.objects.filter(is_deleted=False).order_by(
        "-collection_date", "-collection_time"
    )
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
            # `trip_assignment_id`/`trip_plan_id` are plain CharFields now (no
            # FK to traverse with `__`), so resolve the supervisor's trip
            # plans -> trip assignments -> unique_ids explicitly instead.
            supervisor_id = getattr(self.request.user, "unique_id", None) or self.request.user
            trip_plan_ids = TripPlan.objects.filter(
                supervisor_id=supervisor_id
            ).values_list("unique_id", flat=True)
            trip_assignment_ids = DailyTripAssignment.objects.filter(
                trip_plan_id__in=trip_plan_ids
            ).values_list("unique_id", flat=True)
            queryset = queryset.filter(trip_assignment_id__in=list(trip_assignment_ids))

        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(collection_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(collection_date__lte=date_to)

        return queryset
