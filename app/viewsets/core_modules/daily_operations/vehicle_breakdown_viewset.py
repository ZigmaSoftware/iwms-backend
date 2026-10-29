from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from app.models.core_modules.daily_operations.vehicle_breakdown import (
    VehicleBreakdown,
    VehicleBreakdownPhoto,
    sync_vehicle_operational_status,
)
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
    VehicleBreakdownSerializer,
    VehicleBreakdownVerifySerializer,
    VehicleBreakdownRejectSerializer,
    VehicleBreakdownMarkRepairedSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadmin_masters.company_scoped_viewset import (
    CompanyScopedViewSet,
    _tenant_value,
)
from app.utils.bulk_upload_mixin import BulkUploadMixin


class VehicleBreakdownViewSet(BulkUploadMixin, AuditViewSetMixin, CompanyScopedViewSet):
    STAFF_ROLE_ALIASES = {
        "driver": "Company Driver",
        "company driver": "Company Driver",
        "govt_panchayat_driver": "Company Driver",
        "operator": "Company Operator",
        "company operator": "Company Operator",
        "govt_panchayat_operator": "Company Operator",
    }
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    # Every relation above (trip_assignment_id, breakdown_vehicle_id,
    # replacement_vehicle_id/driver_id/operator_id, alt_staff_template_id,
    # new_assignment, etc.) is now a plain CharField id column, not a real
    # ForeignKey — select_related can no longer follow them; the serializer
    # resolves each one on demand via its own queries instead.
    queryset = VehicleBreakdown.objects.filter(is_deleted=False)
    serializer_class = VehicleBreakdownSerializer
    lookup_field = "unique_id"
    permission_resource = "VehicleBreakdown"
    filter_backends = [ModelFieldQueryFilter, ModelFieldSearchFilter, SerializerOrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["breakdown_time", "status", "approval_status"]

    AUDIT_MODULE = "schedule-masters"
    AUDIT_ENDPOINT = "vehicle-breakdowns"

    def _scope_company_project(self, qs):
        if self._is_platform_super_admin():
            company_param = self.request.query_params.get("company_id")
            project_param = self.request.query_params.get("project_id")
            if company_param and hasattr(qs.model, "company_id"):
                qs = qs.filter(company_id=company_param)
            if project_param and hasattr(qs.model, "project_id"):
                qs = qs.filter(project_id=project_param)
            return qs

        # _project() returns a Project instance; _tenant_value converts it to
        # the unique_id string for CharField project_id columns.
        company = self._company()
        if company and hasattr(qs.model, "company_id"):
            qs = qs.filter(company_id=_tenant_value(qs.model, "company_id", company))

        project = self._project()
        if project and hasattr(qs.model, "project_id"):
            qs = qs.filter(project_id=_tenant_value(qs.model, "project_id", project))

        return qs

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

        if self._is_supervisor_user() or str(params.get("mine", "")).lower() in {
            "true",
            "1",
            "yes",
        }:
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan
            from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment

            supervised_plan_ids = TripPlan.objects.filter(
                supervisor_id=self.request.user.staff_unique_id,
            ).values("unique_id")
            supervised_assignment_ids = DailyTripAssignment.objects.filter(
                trip_plan_id__in=supervised_plan_ids,
            ).values("unique_id")
            qs = qs.filter(trip_assignment_id__in=supervised_assignment_ids)

        if trip_date:
            matching_assignment_ids = DailyTripAssignment.objects.filter(
                trip_date=trip_date,
            ).values("unique_id")
            qs = qs.filter(trip_assignment_id__in=matching_assignment_ids)
        if trip_assignment:
            qs = qs.filter(trip_assignment_id=trip_assignment)
        if approval_status:
            qs = qs.filter(approval_status=approval_status)
        if breakdown_status:
            qs = qs.filter(status=breakdown_status)
        if breakdown_reason:
            qs = qs.filter(breakdown_reason=breakdown_reason)
        if project:
            qs = qs.filter(project_id=project)
        if search:
            matching_vehicle_ids = VehicleCreation.objects.filter(
                vehicle_no__icontains=search,
            ).values("unique_id")
            matching_staff_ids = Staffcreation.objects.filter(
                employee_name__icontains=search,
            ).values("staff_unique_id")
            qs = qs.filter(
                Q(unique_id__icontains=search)
                | Q(trip_assignment_id__icontains=search)
                | Q(breakdown_vehicle_id__in=matching_vehicle_ids)
                | Q(replacement_vehicle_id__in=matching_vehicle_ids)
                | Q(replacement_driver_id__in=matching_staff_ids)
                | Q(replacement_operator_id__in=matching_staff_ids)
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
        sync_vehicle_operational_status(instance.breakdown_vehicle_id)
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

        data = VehicleBreakdownSerializer(instance, context={"request": request}).data
        # Upcoming trips that could not move (replacement already booked then).
        data["skipped_moves"] = getattr(instance, "skipped_moves", [])
        # Trip plans that now run on the replacement until the repair.
        data["substituted_plan_ids"] = getattr(instance, "substituted_plan_ids", [])
        return Response(data, status=status.HTTP_200_OK)

    # ── verify-preview action ─────────────────────────────────────────
    # What Verify & Approve will offer for a replacement vehicle: the broken
    # vehicle's not-started trips and its trip plans, each with the work the
    # replacement already has then, plus the crew that carries on by default.

    @action(detail=True, methods=["get"], url_path="verify-preview")
    def verify_preview(self, request, unique_id=None):
        from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
            original_crew_template,
        )
        from app.services import vehicle_substitution

        instance = self.get_object()
        replacement_vehicle_id = (
            request.query_params.get("replacement_vehicle_id")
            or instance.replacement_vehicle_id
        )
        data = vehicle_substitution.verify_preview(instance, replacement_vehicle_id)
        crew = original_crew_template(instance)
        data["original_crew"] = {
            "driver": getattr(getattr(crew, "driver", None), "employee_name", None),
            "operator": getattr(getattr(crew, "operator", None), "employee_name", None),
        } if crew else None
        return Response(data)

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

    # ── mark-repaired action ──────────────────────────────────────────
    # The broken vehicle is fixed: closes the breakdown and moves the
    # vehicle from BREAKDOWN back to ACTIVE.

    @swagger_auto_schema(request_body=VehicleBreakdownMarkRepairedSerializer)
    @action(detail=True, methods=["patch"], url_path="mark-repaired")
    def mark_repaired(self, request, unique_id=None):
        instance = self.get_object()
        serializer = VehicleBreakdownMarkRepairedSerializer(
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

    # ── available-staff action ────────────────────────────────────────
    # Returns this supervisor's staff who are not already assigned to another
    # Scheduled/In-Progress trip on the given date. The broken trip is excluded
    # so its existing crew can continue with the replacement vehicle.

    @action(detail=False, methods=["get"], url_path="available-staff")
    def available_staff(self, request):
        trip_date = request.query_params.get("date")
        requested_role = (request.query_params.get("role") or "").strip()
        role = self.STAFF_ROLE_ALIASES.get(requested_role.lower())
        if not trip_date:
            return Response(
                {"detail": "date query param is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not requested_role:
            return Response(
                {"detail": "role query param is required (e.g. 'Company Driver')."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not role:
            return Response(
                {"detail": "role must identify a driver or operator."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        excluded_assignment_id = None
        breakdown_id = request.query_params.get("breakdown_id")
        if breakdown_id:
            breakdown = self._scope_company_project(
                VehicleBreakdown.objects.filter(
                    unique_id=breakdown_id,
                    is_deleted=False,
                )
            ).first()
            assignment = breakdown.trip_assignment if breakdown else None
            if (
                assignment
                and (
                    not self._is_supervisor_user()
                    or getattr(assignment.trip_plan, "supervisor_id", None)
                    == self.request.user.staff_unique_id
                )
            ):
                excluded_assignment_id = breakdown.trip_assignment_id

        active_assignments = self._scope_company_project(DailyTripAssignment.objects.filter(
            trip_date=trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        ))
        if excluded_assignment_id:
            active_assignments = active_assignments.exclude(
                unique_id=excluded_assignment_id
            )

        busy_driver_ids = set()
        busy_operator_ids = set()
        for a in active_assignments:
            tmpl = a.alt_staff_template or a.staff_template
            if not tmpl:
                continue
            if tmpl.driver_id:
                busy_driver_ids.add(tmpl.driver_id)
            if tmpl.operator_id:
                busy_operator_ids.add(tmpl.operator_id)

        matching_staffusertype_ids = StaffUserType.objects.filter(
            name__iexact=role,
            is_deleted=False,
        ).values("unique_id")
        qs = Staffcreation.objects.filter(
            is_deleted=False,
            active_status=True,
            staffusertype_id__in=matching_staffusertype_ids,
        )

        if role == "Company Driver":
            qs = qs.exclude(staff_unique_id__in=busy_driver_ids)
        elif role == "Company Operator":
            qs = qs.exclude(staff_unique_id__in=busy_operator_ids)

        qs = self._scope_company_project(qs)

        if self._is_supervisor_user():
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan
            from app.models.core_modules.schedule_setup.staff_template import StaffTemplate

            supervisor_id = self.request.user.staff_unique_id
            supervised_template_ids = TripPlan.objects.filter(
                supervisor_id=supervisor_id,
                is_deleted=False,
            ).exclude(staff_template_id__isnull=True).values_list(
                "staff_template_id", flat=True
            )
            supervised_staff_ids = set(
                StaffTemplate.objects.filter(unique_id__in=supervised_template_ids)
                .exclude(driver_id__isnull=True)
                .values_list("driver_id", flat=True)
            ) | set(
                StaffTemplate.objects.filter(unique_id__in=supervised_template_ids)
                .exclude(operator_id__isnull=True)
                .values_list("operator_id", flat=True)
            )
            qs = qs.filter(
                Q(staff_head_id=supervisor_id)
                | Q(staff_unique_id__in=supervised_staff_ids)
            ).distinct()

        data = [
            {
                "staff_unique_id": s.staff_unique_id,
                "employee_name": s.employee_name,
            }
            for s in qs.order_by("employee_name")
        ]
        return Response(data)

    # ── available-staff-templates action ──────────────────────────────
    # Returns active staff templates whose driver/operator are not on a
    # Scheduled/In-Progress trip for the date. Templates from completed trips
    # remain available.

    @action(detail=False, methods=["get"], url_path="available-staff-templates")
    def available_staff_templates(self, request):
        from app.models.core_modules.schedule_setup.staff_template import StaffTemplate

        trip_date = request.query_params.get("date")
        if not trip_date:
            return Response(
                {"detail": "date query param is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_assignments = self._scope_company_project(DailyTripAssignment.objects.filter(
            trip_date=trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        ))
        # ?trip_assignment_id = the trip that broke down. Its own crew is
        # "busy" only on that trip and on its vehicle's later trips that day,
        # so leave those out — the same crew can carry on with the
        # replacement vehicle.
        broken_trip = DailyTripAssignment.objects.filter(
            unique_id=request.query_params.get("trip_assignment_id") or "",
            is_deleted=False,
        ).first()
        if broken_trip:
            active_assignments = active_assignments.exclude(
                Q(pk=broken_trip.pk)
                | Q(
                    vehicle_id=broken_trip.vehicle_id,
                    status=DailyTripAssignment.STATUS_SCHEDULED,
                    actual_start_at__isnull=True,
                )
            )

        busy_driver_ids = set()
        busy_operator_ids = set()
        for assignment in active_assignments:
            template = assignment.alt_staff_template or assignment.staff_template
            if not template:
                continue
            if template.driver_id:
                busy_driver_ids.add(template.driver_id)
            if template.operator_id:
                busy_operator_ids.add(template.operator_id)

        current_breakdown_id = request.query_params.get("exclude_id")
        matching_assignment_ids = DailyTripAssignment.objects.filter(
            trip_date=trip_date,
        ).values("unique_id")
        pending_breakdowns = self._scope_company_project(VehicleBreakdown.objects.filter(
            trip_assignment_id__in=matching_assignment_ids,
            approval_status=VehicleBreakdown.APPROVAL_PENDING,
            is_deleted=False,
        ))
        if current_breakdown_id:
            pending_breakdowns = pending_breakdowns.exclude(unique_id=current_breakdown_id)

        busy_driver_ids.update(
            pending_breakdowns.exclude(replacement_driver_id__isnull=True)
            .values_list("replacement_driver_id", flat=True)
        )
        busy_operator_ids.update(
            pending_breakdowns.exclude(replacement_operator_id__isnull=True)
            .values_list("replacement_operator_id", flat=True)
        )

        qs = StaffTemplate.objects.filter(
            is_deleted=False,
            is_active=True,
            status=StaffTemplate.Status.ACTIVE,
        )
        qs = self._scope_company_project(qs)
        qs = qs.exclude(
            Q(driver_id__in=busy_driver_ids)
            | Q(operator_id__in=busy_operator_ids)
        )

        data = [
            {
                "unique_id": template.unique_id,
                "display_code": template.display_code,
                "driver_id": template.driver_id,
                "driver_name": getattr(template.driver, "employee_name", None),
                "operator_id": template.operator_id,
                "operator_name": getattr(template.operator, "employee_name", None),
            }
            for template in qs.order_by("display_code")
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

        busy_vehicle_ids = self._scope_company_project(DailyTripAssignment.objects.filter(
            trip_date=trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        )).values_list("vehicle_id", flat=True)

        # When editing an existing breakdown, exclude it from the pending filter
        # so its own replacement vehicle is still shown as available.
        current_breakdown_id = request.query_params.get("exclude_id")
        matching_assignment_ids = DailyTripAssignment.objects.filter(
            trip_date=trip_date,
        ).values("unique_id")
        pending_qs = self._scope_company_project(VehicleBreakdown.objects.filter(
            trip_assignment_id__in=matching_assignment_ids,
            approval_status=VehicleBreakdown.APPROVAL_PENDING,
            replacement_vehicle_id__isnull=False,
            is_deleted=False,
        ))
        if current_breakdown_id:
            pending_qs = pending_qs.exclude(unique_id=current_breakdown_id)
        pending_replacement_ids = pending_qs.values_list("replacement_vehicle_id", flat=True)

        qs = VehicleCreation.objects.filter(
            is_deleted=False,
            is_active=True,
            operational_status=VehicleCreation.OperationalStatus.ACTIVE,
        ).exclude(unique_id__in=busy_vehicle_ids).exclude(unique_id__in=pending_replacement_ids)

        qs = self._scope_company_project(qs)

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
        sync_vehicle_operational_status(instance.breakdown_vehicle_id)

        photos = self.request.FILES.getlist("photos")
        for photo in photos:
            VehicleBreakdownPhoto.objects.create(breakdown_id=instance.unique_id, photo=photo)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=self._serialize_instance(instance),
        )

        from app.models.core_modules.notifications.staff_notification import StaffNotification
        from app.services.staff_notification_service import notify_staff

        # The *_id fields are plain id strings — resolve the related rows via
        # the model properties so the supervisor is actually found.
        assignment = instance.trip_assignment
        trip_plan = assignment.trip_plan if assignment else None
        supervisor = trip_plan.supervisor if trip_plan else None
        if supervisor is not None:
            vehicle_no = getattr(instance.breakdown_vehicle, "vehicle_no", None) or "A vehicle"
            notify_staff(
                supervisor,
                StaffNotification.TYPE_VEHICLE_BREAKDOWN_REPORTED,
                title="Vehicle breakdown reported",
                body=f"{vehicle_no} broke down on trip {assignment.unique_id}.",
                data={
                    "vehicle_breakdown_id": instance.unique_id,
                    "trip_assignment_id": assignment.unique_id,
                    "latitude": str(instance.breakdown_lat or ""),
                    "longitude": str(instance.breakdown_lng or ""),
                },
            )

    def perform_update(self, serializer):
        previous_data = self._serialize_instance(serializer.instance)
        previous_vehicle_id = serializer.instance.breakdown_vehicle_id
        super().perform_update(serializer)
        instance = serializer.instance
        # The breakdown may have been moved to another vehicle.
        for vehicle_id in {previous_vehicle_id, instance.breakdown_vehicle_id}:
            sync_vehicle_operational_status(vehicle_id)
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
