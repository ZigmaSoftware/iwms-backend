from decimal import Decimal

from django.db.models import Sum
from rest_framework import status
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.daily_trip_log import DailyTripLog
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

    def _upsert_trip_log_for_assignment(self, assignment):
        if not assignment:
            return

        children = assignment.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return

        all_collected = not children.filter(is_collected=False).exists()
        total_weight = children.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
        vehicle_capacity = getattr(getattr(assignment, "vehicle_id", None), "capacity", None)
        trip_capacity = getattr(getattr(assignment, "trip_plan_id", None), "max_vehicle_capacity_kg", None)
        capacity = vehicle_capacity or trip_capacity
        exceeds_capacity = (
            bool(capacity)
            and total_weight
            and Decimal(str(total_weight)) > Decimal(str(capacity))
        )
        stored_weight = None if exceeds_capacity else total_weight
        log_status = (
            DailyTripLog.LOG_STATUS_SUBMITTED
            if all_collected and stored_weight
            else DailyTripLog.LOG_STATUS_DRAFT
        )
        remarks = (
            "Auto-generated from daily trip collection points; total weight exceeds capacity."
            if exceeds_capacity
            else "Auto-generated from daily trip collection points."
        )

        log, created = DailyTripLog.objects.get_or_create(
            trip_assignment_id=assignment,
            defaults={
                "collected_weight_kg": stored_weight,
                "log_status": log_status,
                "remarks": remarks,
            },
        )
        if created or log.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            return

        log.collected_weight_kg = stored_weight
        log.log_status = log_status
        log.remarks = log.remarks or remarks
        log.save()

    def _sync_assignment_and_log(self, instance):
        if not instance:
            return
        assignment = instance.trip_assignment_id
        if instance.is_collected:
            assignment.mark_completed_if_all_cps_collected()
        self._upsert_trip_log_for_assignment(assignment)

    def get_queryset(self):
        queryset = (
            DailyTripCollectionPoint.objects.select_related(
                "company_id",
                "project_id",
                "trip_assignment_id",
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
            queryset = queryset.filter(company_id__unique_id=company)
        if project:
            queryset = queryset.filter(project_id__unique_id=project)
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

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_assignment_and_log(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_assignment_and_log(serializer.instance)

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
