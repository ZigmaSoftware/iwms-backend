from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.transport_masters.daily_trip_log import DailyTripLog
from app.serializers.transport_masters.daily_trip_log_serializer import (
    DailyTripLogSerializer,
    DailyTripLogVerifySerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class DailyTripLogViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = (
        DailyTripLog.objects.select_related(
            "company_id",
            "project_id",
            "trip_assignment_id",
            "trip_assignment_id__trip_definition_id",
            "trip_assignment_id__trip_definition_id__routeplan_id",
            "panchayat_id",
            "collection_point_id",
            "waste_type_id",
            "driver_id",
            "operator_id",
            "vehicle_id",
            "verified_by",
            "verified_by__staff",
            "verified_by__user",
        )
        .prefetch_related("bin_ids", "extra_operator_ids")
        .filter(is_deleted=False)
    )
    serializer_class = DailyTripLogSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripLog"
    pagination_class = LimitOffsetWithPage

    AUDIT_MODULE = "trip-logs"
    AUDIT_ENDPOINT = "daily-trip-logs"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        trip_date = params.get("date") or params.get("trip_date")
        status_value = params.get("status") or params.get("log_status")
        assignment = params.get("trip_assignment_id")
        panchayat = params.get("panchayat_id")
        collection_point = params.get("collection_point_id")
        waste_type = params.get("waste_type_id")
        driver = params.get("driver_id")
        operator = params.get("operator_id")
        search = params.get("search") or params.get("q")

        if trip_date:
            qs = qs.filter(trip_date=trip_date)
        if status_value:
            qs = qs.filter(log_status=status_value)
        if assignment:
            qs = qs.filter(trip_assignment_id=assignment)
        if panchayat:
            qs = qs.filter(panchayat_id=panchayat)
        if collection_point:
            qs = qs.filter(collection_point_id=collection_point)
        if waste_type:
            qs = qs.filter(waste_type_id=waste_type)
        if driver:
            qs = qs.filter(driver_id=driver)
        if operator:
            qs = qs.filter(operator_id=operator)
        if search:
            qs = qs.filter(
                Q(unique_id__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
                | Q(collection_point_id__cp_name__icontains=search)
                | Q(waste_type_id__waste_type_name__icontains=search)
                | Q(driver_id__employee_name__icontains=search)
                | Q(operator_id__employee_name__icontains=search)
                | Q(vehicle_id__vehicle_no__icontains=search)
            )

        ordering = params.get("ordering")
        allowed_ordering = {
            "unique_id",
            "-unique_id",
            "trip_date",
            "-trip_date",
            "collected_weight_kg",
            "-collected_weight_kg",
            "log_status",
            "-log_status",
            "created_at",
            "-created_at",
        }
        if ordering in allowed_ordering:
            qs = qs.order_by(ordering)

        return qs

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            return Response(
                {"detail": "Verified trip logs are read-only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Verified trip logs are read-only.")

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

    @swagger_auto_schema(request_body=DailyTripLogVerifySerializer)
    @action(detail=True, methods=["patch"], url_path="verify")
    def verify(self, request, unique_id=None):
        instance = self.get_object()
        serializer = DailyTripLogVerifySerializer(
            data=request.data,
            context={
                "instance": instance,
                "request": request,
                "account": self._get_account(),
            },
        )
        serializer.is_valid(raise_exception=True)

        previous_data = self._serialize_instance(instance)
        instance = serializer.save()
        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            DailyTripLogSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def perform_create(self, serializer):
        previous_data = None
        super().perform_create(serializer)
        instance = serializer.instance
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

    def perform_update(self, serializer):
        previous_data = self._serialize_instance(serializer.instance)
        super().perform_update(serializer)
        instance = serializer.instance
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
