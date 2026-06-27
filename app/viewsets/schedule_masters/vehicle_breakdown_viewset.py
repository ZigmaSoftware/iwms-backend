from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.schedule_masters.vehicle_breakdown import VehicleBreakdown
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.serializers.schedule_masters.vehicle_breakdown_serializer import (
    VehicleBreakdownSerializer,
    VehicleBreakdownVerifySerializer,
    VehicleBreakdownRejectSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class VehicleBreakdownViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = (
        VehicleBreakdown.objects.select_related(
            "company_id",
            "project_id",
            "trip_assignment_id",
            "trip_assignment_id__trip_plan_id",
            "trip_assignment_id__staff_template_id",
            "trip_assignment_id__staff_template_id__driver_id",
            "trip_assignment_id__staff_template_id__operator_id",
            "trip_assignment_id__panchayat_id",
            "breakdown_vehicle_id",
            "replacement_vehicle_id",
            "replacement_driver_id",
            "replacement_operator_id",
            "alt_staff_template_id",
            "approved_by",
        )
        .filter(is_deleted=False)
    )
    serializer_class = VehicleBreakdownSerializer
    lookup_field = "unique_id"
    permission_resource = "VehicleBreakdown"

    AUDIT_MODULE = "schedule-masters"
    AUDIT_ENDPOINT = "vehicle-breakdowns"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        trip_date = params.get("date") or params.get("trip_date")
        trip_assignment = params.get("trip_assignment_id")
        approval_status = params.get("approval_status")
        breakdown_status = params.get("status")
        breakdown_reason = params.get("breakdown_reason")
        search = params.get("search") or params.get("q")
        project = params.get("project_id")

        if trip_date:
            qs = qs.filter(trip_assignment_id__trip_date=trip_date)
        if trip_assignment:
            qs = qs.filter(trip_assignment_id__unique_id=trip_assignment)
        if approval_status:
            qs = qs.filter(approval_status=approval_status)
        if breakdown_status:
            qs = qs.filter(status=breakdown_status)
        if breakdown_reason:
            qs = qs.filter(breakdown_reason=breakdown_reason)
        if project:
            qs = qs.filter(project_id__unique_id=project)
        if search:
            qs = qs.filter(
                Q(unique_id__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
                | Q(breakdown_vehicle_id__vehicle_no__icontains=search)
                | Q(replacement_vehicle_id__vehicle_no__icontains=search)
                | Q(replacement_driver_id__employee_name__icontains=search)
                | Q(replacement_operator_id__employee_name__icontains=search)
            )

        return qs

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            return Response(
                {"detail": "Approved breakdown records are read-only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Approved breakdown records cannot be deleted.")

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

    # ── verify action (mirrors DailyTripLogViewSet.verify) ───────────

    @swagger_auto_schema(request_body=VehicleBreakdownVerifySerializer)
    @action(detail=True, methods=["patch"], url_path="verify")
    def verify(self, request, unique_id=None):
        instance = self.get_object()
        serializer = VehicleBreakdownVerifySerializer(
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
            VehicleBreakdownSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ── reject action ─────────────────────────────────────────────────

    @swagger_auto_schema(request_body=VehicleBreakdownRejectSerializer)
    @action(detail=True, methods=["patch"], url_path="reject")
    def reject(self, request, unique_id=None):
        instance = self.get_object()
        serializer = VehicleBreakdownRejectSerializer(
            data=request.data,
            context={
                "instance": instance,
                "request": request,
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
            VehicleBreakdownSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ── available-staff action ────────────────────────────────────────
    # Returns staff NOT already assigned to any Scheduled/In-Progress trip on the given date.
    # role param: "Company Driver" or "Company Operator"

    @action(detail=False, methods=["get"], url_path="available-staff")
    def available_staff(self, request):
        from app.models.user_creations.staffcreation import Staffcreation
        from app.models.schedule_masters.staff_template import StaffTemplate
        from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate

        trip_date = request.query_params.get("date")
        role = request.query_params.get("role")
        if not trip_date:
            return Response(
                {"detail": "date query param is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not role:
            return Response(
                {"detail": "role query param is required (e.g. 'Company Driver')."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_assignments = DailyTripAssignment.objects.filter(
            trip_date=trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        ).select_related("staff_template_id", "alt_staff_template_id")

        busy_driver_ids = set()
        busy_operator_ids = set()
        for a in active_assignments:
            tmpl = a.alt_staff_template_id or a.staff_template_id
            if not tmpl:
                continue
            if tmpl.driver_id_id:
                busy_driver_ids.add(tmpl.driver_id_id)
            if tmpl.operator_id_id:
                busy_operator_ids.add(tmpl.operator_id_id)

        qs = Staffcreation.objects.filter(
            is_deleted=False,
            active_status=True,
            staffusertype_id__name=role,
        )

        if role == "Company Driver":
            qs = qs.exclude(staff_unique_id__in=busy_driver_ids)
        elif role == "Company Operator":
            qs = qs.exclude(staff_unique_id__in=busy_operator_ids)

        if not self._is_platform_super_admin():
            company_param = request.query_params.get("company_id")
            project_param = request.query_params.get("project_id")
            if company_param:
                qs = qs.filter(company_id__unique_id=company_param)
            if project_param:
                qs = qs.filter(project_id__unique_id=project_param)

        data = [
            {
                "staff_unique_id": s.staff_unique_id,
                "employee_name": s.employee_name,
            }
            for s in qs.order_by("employee_name")
        ]
        return Response(data)

    # ── available-vehicles action ─────────────────────────────────────
    # Returns vehicles NOT assigned to any Scheduled/In-Progress trip on the given date.

    @action(detail=False, methods=["get"], url_path="available-vehicles")
    def available_vehicles(self, request):
        trip_date = request.query_params.get("date")
        if not trip_date:
            return Response(
                {"detail": "date query param is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        busy_vehicle_ids = DailyTripAssignment.objects.filter(
            trip_date=trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        ).values_list("vehicle_id", flat=True)

        pending_replacement_ids = VehicleBreakdown.objects.filter(
            trip_assignment_id__trip_date=trip_date,
            approval_status=VehicleBreakdown.APPROVAL_PENDING,
            replacement_vehicle_id__isnull=False,
            is_deleted=False,
        ).values_list("replacement_vehicle_id", flat=True)

        qs = VehicleCreation.objects.filter(
            is_deleted=False,
            is_active=True,
        ).exclude(unique_id__in=busy_vehicle_ids).exclude(unique_id__in=pending_replacement_ids)

        # Company/project scope for non-superadmin
        if not self._is_platform_super_admin():
            company_param = request.query_params.get("company_id")
            project_param = request.query_params.get("project_id")
            if company_param:
                qs = qs.filter(company_id__unique_id=company_param)
            if project_param:
                qs = qs.filter(project_id__unique_id=project_param)

        data = [
            {
                "unique_id": v.unique_id,
                "vehicle_no": v.vehicle_no,
                "capacity": str(v.capacity) if v.capacity else None,
            }
            for v in qs.order_by("vehicle_no")
        ]
        return Response(data)

    # ── audit hooks ───────────────────────────────────────────────────

    def perform_create(self, serializer):
        super().perform_create(serializer)
        instance = serializer.instance
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
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
