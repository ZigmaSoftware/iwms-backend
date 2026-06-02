from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.serializers.schedule_masters.trip_plan_collection_point_serializer import (
    TripPlanCollectionPointSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class TripPlanCollectionPointViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = TripPlanCollectionPointSerializer
    lookup_field = "unique_id"
    permission_resource = "TripPlanCollectionPoint"

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "trip-plan-collection-points"

    def get_queryset(self):
        queryset = (
            TripPlanCollectionPoint.objects.select_related(
                "trip_plan_id",
                "trip_plan_id__company_id",
                "trip_plan_id__project_id",
                "collection_point_id",
                "bin_id",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        trip_plan = params.get("trip_plan_id")
        company = params.get("company_id")
        project = params.get("project_id")
        collection_point = params.get("collection_point_id")

        if trip_plan:
            queryset = queryset.filter(trip_plan_id__unique_id=trip_plan)
        if company:
            queryset = queryset.filter(trip_plan_id__company_id__unique_id=company)
        if project:
            queryset = queryset.filter(trip_plan_id__project_id__unique_id=project)
        if collection_point:
            queryset = queryset.filter(collection_point_id__unique_id=collection_point)

        return queryset
