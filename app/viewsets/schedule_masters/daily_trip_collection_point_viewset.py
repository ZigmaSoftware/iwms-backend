from rest_framework import status
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.serializers.schedule_masters.daily_trip_collection_point_serializer import (
    DailyTripCollectionPointSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class DailyTripCollectionPointViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = DailyTripCollectionPointSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripCollectionPoint"

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "daily-trip-collection-point"

    def get_queryset(self):
        queryset = (
            DailyTripCollectionPoint.objects.select_related(
                "trip_assignment_id",
                "trip_assignment_id__company_id",
                "trip_assignment_id__project_id",
                "trip_assignment_id__trip_plan_id",
                "collection_point_id",
                "collection_point_id__panchayat_id",
                "collection_point_id__ward_id",
                "bin_id",
                "bin_id__wastetype_id",
                "collected_by",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        assignment = params.get("trip_assignment_id")
        company = params.get("company_id")
        project = params.get("project_id")
        collection_point = params.get("collection_point_id")
        bin_id = params.get("bin_id")
        status_value = params.get("status")
        is_collected = params.get("is_collected")

        if company:
            queryset = queryset.filter(trip_assignment_id__company_id__unique_id=company)
        if project:
            queryset = queryset.filter(trip_assignment_id__project_id__unique_id=project)
        if assignment:
            queryset = queryset.filter(trip_assignment_id__unique_id=assignment)
        if collection_point:
            queryset = queryset.filter(collection_point_id__unique_id=collection_point)
        if bin_id:
            queryset = queryset.filter(bin_id__unique_id=bin_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if is_collected is not None:
            queryset = queryset.filter(
                is_collected=str(is_collected).lower() in {"1", "true", "yes"}
            )

        return queryset

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_collected:
            return Response(
                {"detail": "Collected trip collection points are read-only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        previous_data = self._serialize_instance(instance)
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active", "updated_at"])
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
