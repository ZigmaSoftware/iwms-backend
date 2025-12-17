from datetime import date

from django.db import models
from django.db.models import Count, Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.apps.assignment import (
    AssignmentStatusHistory,
    DailyAssignment,
    DriverCollectionLog,
)
from api.serializers.desktopView.assignments.assignment_serializer import (
    AssignmentStatusHistorySerializer,
    DailyAssignmentSerializer,
    DriverCollectionLogSerializer,
    EnhancedAssignmentSerializer,
)


class DailyAssignmentViewSet(viewsets.ModelViewSet):
    """
    Primary assignment viewset with status tracking.
    """

    lookup_field = "unique_id"
    queryset = DailyAssignment.objects.all()
    serializer_class = DailyAssignmentSerializer

    def get_queryset(self):
        base_qs = DailyAssignment.objects.filter(is_active=True)

        if self.action in ["retrieve", "complete", "cancel", "skip"]:
            base_qs = base_qs.select_related(
                "ward",
                "driver",
                "operator",
                "driver__staff_id",
                "operator__staff_id",
            ).prefetch_related(
                Prefetch(
                    "status_history",
                    queryset=AssignmentStatusHistory.objects.select_related(
                        "changed_by"
                    ).order_by("-timestamp"),
                ),
                Prefetch(
                    "collection_logs",
                    queryset=DriverCollectionLog.objects.select_related(
                        "driver"
                    ).order_by("-timestamp"),
                ),
            ).annotate(total_status_changes=Count("status_history"))
        else:
            base_qs = base_qs.select_related("ward", "driver", "operator")

        params = self.request.query_params

        if "driver_id" in params:
            base_qs = base_qs.filter(driver__unique_id=params["driver_id"])

        if "operator_id" in params:
            base_qs = base_qs.filter(operator__unique_id=params["operator_id"])

        if "ward_id" in params:
            base_qs = base_qs.filter(ward__unique_id=params["ward_id"])

        if "shift" in params:
            base_qs = base_qs.filter(shift=params["shift"])

        if "assignment_type" in params:
            base_qs = base_qs.filter(assignment_type=params["assignment_type"])

        if "date" in params:
            base_qs = base_qs.filter(date=params["date"])
        elif self.action == "list":
            base_qs = base_qs.filter(date=date.today())

        return base_qs.order_by("shift")

    def get_serializer_class(self):
        if self.action in ["retrieve", "complete", "cancel", "skip"]:
            return EnhancedAssignmentSerializer
        return DailyAssignmentSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        assignment = serializer.save(
            assigned_by=user,
            current_status="pending",
        )
        AssignmentStatusHistory.objects.create(
            assignment=assignment,
            status="created",
            changed_by=user,
            reason="Assignment created",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        reason = request.data.get("reason", "Deleted by admin")

        instance.is_active = False
        instance.current_status = "cancelled"
        instance.cancelled_by = user
        instance.cancelled_at = timezone.now()
        instance.cancelled_reason = reason
        instance.save(
            update_fields=[
                "is_active",
                "current_status",
                "cancelled_by",
                "cancelled_at",
                "cancelled_reason",
            ]
        )

        AssignmentStatusHistory.objects.create(
            assignment=instance,
            status="cancelled",
            changed_by=user,
            reason=reason,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def cancel(self, request, unique_id=None):
        assignment = self.get_object()
        reason = request.data.get("reason")
        if not reason:
            return Response(
                {"reason": "Cancellation reason is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.is_active = False
        assignment.cancelled_reason = reason
        assignment.cancelled_by = request.user
        assignment.cancelled_at = timezone.now()
        assignment.current_status = "cancelled"

        assignment.save(
            update_fields=[
                "is_active",
                "cancelled_reason",
                "cancelled_by",
                "cancelled_at",
                "current_status",
            ]
        )

        AssignmentStatusHistory.objects.create(
            assignment=assignment,
            status="cancelled",
            changed_by=request.user,
            reason=reason,
        )

        serializer = self.get_serializer(assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        old_instance = self.get_object()
        assignment = serializer.save()

        if old_instance.current_status != assignment.current_status:
            AssignmentStatusHistory.objects.create(
                assignment=assignment,
                status=assignment.current_status,
                changed_by=self.request.user
                if self.request.user.is_authenticated
                else None,
                reason=f"Status changed from {old_instance.current_status} to {assignment.current_status}",
            )

    @action(detail=True, methods=["post"])
    def complete(self, request, unique_id=None):
        assignment = self.get_object()
        assignment.current_status = "completed"
        assignment.completed_at = timezone.now()
        assignment.completed_by = request.user if request.user.is_authenticated else None
        assignment.save(
            update_fields=["current_status", "completed_at", "completed_by"]
        )

        AssignmentStatusHistory.objects.create(
            assignment=assignment,
            status="completed",
            changed_by=request.user
            if request.user.is_authenticated
            else None,
            reason="Marked as completed",
        )
        serializer = self.get_serializer(assignment)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def skip(self, request, unique_id=None):
        assignment = self.get_object()
        reason = request.data.get("reason")
        if not reason:
            return Response(
                {"reason": "Skip reason is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment.current_status = "skipped"
        assignment.skipped_at = timezone.now()
        assignment.skipped_by = request.user
        assignment.skip_reason = reason
        assignment.save(
            update_fields=[
                "current_status",
                "skipped_at",
                "skipped_by",
                "skip_reason",
            ]
        )

        AssignmentStatusHistory.objects.create(
            assignment=assignment,
            status="skipped",
            changed_by=request.user,
            reason=reason,
        )
        serializer = self.get_serializer(assignment)
        return Response(serializer.data)


class StaffAssignmentHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for staff assignment history (drivers/operators).
    """

    queryset = DailyAssignment.objects.all()
    serializer_class = EnhancedAssignmentSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = (
            DailyAssignment.objects.select_related(
                "ward",
                "driver",
                "operator",
                "driver__staff_id",
                "operator__staff_id",
            )
            .prefetch_related(
                Prefetch(
                    "status_history",
                    queryset=AssignmentStatusHistory.objects.select_related(
                        "changed_by"
                    ).order_by("-timestamp"),
                ),
                Prefetch(
                    "collection_logs",
                    queryset=DriverCollectionLog.objects.select_related(
                        "driver"
                    ).order_by("-timestamp"),
                ),
            )
            .annotate(total_status_changes=Count("status_history"))
        )

        params = self.request.query_params
        staff_id = params.get("staff_id")
        driver_id = params.get("driver_id")
        operator_id = params.get("operator_id")
        status_param = params.get("status")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if staff_id:
            qs = qs.filter(
                models.Q(driver__unique_id=staff_id)
                | models.Q(operator__unique_id=staff_id)
            )
        if driver_id:
            qs = qs.filter(driver__unique_id=driver_id)
        if operator_id:
            qs = qs.filter(operator__unique_id=operator_id)
        if status_param:
            qs = qs.filter(current_status=status_param)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        return qs.order_by("-date", "-created_at")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        staff_id = request.query_params.get("staff_id")
        if not staff_id:
            return Response(
                {"error": "staff_id parameter required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = self.get_queryset().filter(
            models.Q(driver__unique_id=staff_id)
            | models.Q(operator__unique_id=staff_id)
        )

        summary = {
            "total_assignments": qs.count(),
            "completed": qs.filter(current_status="completed").count(),
            "skipped": qs.filter(current_status="skipped").count(),
            "cancelled": qs.filter(current_status="cancelled").count(),
            "in_progress": qs.filter(current_status="in_progress").count(),
            "pending": qs.filter(current_status="pending").count(),
        }

        return Response(summary)


class DriverCollectionLogViewSet(viewsets.ModelViewSet):
    """
    Driver collection log viewset.
    """

    serializer_class = DriverCollectionLogSerializer
    queryset = DriverCollectionLog.objects.select_related(
        "assignment", "driver"
    ).all()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if "assignment_id" in params:
            qs = qs.filter(assignment__unique_id=params["assignment_id"])
        if "driver_id" in params:
            qs = qs.filter(driver__unique_id=params["driver_id"])
        return qs.order_by("-timestamp")

    def perform_create(self, serializer):
        driver = None
        if serializer.validated_data.get("driver"):
            driver = serializer.validated_data.get("driver")
        elif self.request.user.is_authenticated:
            driver = self.request.user

        log = serializer.save(driver=driver)
        assignment = log.assignment

        if log.action == "collection_completed":
            assignment.current_status = "completed"
            assignment.completed_at = timezone.now()
            assignment.completed_by = log.driver
            AssignmentStatusHistory.objects.create(
                assignment=assignment,
                status="completed",
                changed_by=log.driver,
                reason="Collection completed by driver",
                metadata={
                    "waste_weight": str(log.waste_weight)
                    if log.waste_weight
                    else None
                },
                latitude=log.latitude,
                longitude=log.longitude,
            )
        elif log.action == "skipped":
            assignment.current_status = "skipped"
            assignment.skipped_at = timezone.now()
            assignment.skipped_by = log.driver
            assignment.skip_reason = log.skip_reason
            AssignmentStatusHistory.objects.create(
                assignment=assignment,
                status="skipped",
                changed_by=log.driver,
                reason=log.skip_reason,
                latitude=log.latitude,
                longitude=log.longitude,
            )
        elif log.action == "started_navigation":
            assignment.current_status = "in_progress"

        assignment.save(
            update_fields=[
                "current_status",
                "completed_at",
                "completed_by",
                "skipped_at",
                "skipped_by",
                "skip_reason",
            ]
        )


class CitizenAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View assignments grouped by citizen/customer (ward/customer filters).
    """

    serializer_class = EnhancedAssignmentSerializer
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = (
            DailyAssignment.objects.select_related(
                "ward",
                "driver",
                "operator",
                "driver__staff_id",
                "operator__staff_id",
                "customer",
            )
            .prefetch_related(
                Prefetch(
                    "status_history",
                    queryset=AssignmentStatusHistory.objects.select_related(
                        "changed_by"
                    ).order_by("-timestamp"),
                ),
                Prefetch(
                    "collection_logs",
                    queryset=DriverCollectionLog.objects.select_related(
                        "driver"
                    ).order_by("-timestamp"),
                ),
            )
            .annotate(total_status_changes=Count("status_history"))
        )

        params = self.request.query_params
        ward_id = params.get("ward_id")
        customer_id = params.get("customer_id")
        status_param = params.get("status")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        if ward_id:
            qs = qs.filter(ward__unique_id=ward_id)
        if customer_id:
            qs = qs.filter(customer__unique_id=customer_id)
        if status_param:
            qs = qs.filter(current_status=status_param)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        return qs.order_by("-date", "-created_at")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.get_queryset()
        ward_id = request.query_params.get("ward_id")
        if ward_id:
            qs = qs.filter(ward__unique_id=ward_id)

        summary = {
            "total_assignments": qs.count(),
            "completed": qs.filter(current_status="completed").count(),
            "skipped": qs.filter(current_status="skipped").count(),
            "cancelled": qs.filter(current_status="cancelled").count(),
            "in_progress": qs.filter(current_status="in_progress").count(),
            "pending": qs.filter(current_status="pending").count(),
        }

        return Response(summary)
