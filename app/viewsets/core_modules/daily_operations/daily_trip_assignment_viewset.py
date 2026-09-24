from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from datetime import datetime, time as datetime_time, timedelta

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response

from app.management.commands.generate_daily_trips import run_for_date
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.daily_operations.scheduler_config import SchedulerConfig
from app.services.daily_trip_scheduler import (
    notify_scheduler_config_changed,
    run_daily_trip_job,
    scheduler_status as get_scheduler_status,
)
from app.serializers.core_modules.daily_operations.daily_trip_assignment_serializer import (
    DailyTripAssignmentSerializer,
    DailyTripAssignmentStatusSerializer,
    DailyTripAssignmentApprovalSerializer,
)
from rest_framework import filters
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class DailyTripAssignmentViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    """
    CRUD + state-machine actions for daily trip assignments.

    Custom actions:
      PATCH  /{unique_id}/status/    — state machine transition
      PATCH  /{unique_id}/approval/  — approval flow (supervisor/admin only)
    """

    # Every relation below (trip_plan_id, staff_template_id, panchayat_id,
    # vehicle_id, wards, driver_id/operator_id, etc.) is now a plain CharField
    # holding the related row's unique_id rather than a real ForeignKey/M2M,
    # so select_related/prefetch_related can no longer follow them — the
    # serializer resolves each one on demand via its own queries instead.
    queryset = DailyTripAssignment.objects.filter(is_deleted=False)

    serializer_class = DailyTripAssignmentSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripAssignment"

    # search_fields used to be DB-level join paths for DRF's SearchFilter,
    # but every relation they crossed (trip_plan_id, staff_template_id,
    # panchayat_id, wards, ...) is now a plain CharField/TextField id column,
    # not a real FK/M2M — no longer joinable at the DB level. Search is
    # applied in Python in get_queryset() instead (see _search_filter below).
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["unique_id", "trip_date", "scheduled_time", "status", "approval_status"]

    AUDIT_MODULE = "trip-assignments"
    AUDIT_ENDPOINT = "daily-trip-assignments"

    def _scheduler_config_payload(self, config):
        now = timezone.localtime()
        run_at_today = datetime.combine(now.date(), config.run_time, tzinfo=now.tzinfo)
        next_run = run_at_today if run_at_today > now else run_at_today + timedelta(days=1)
        return {
            "run_time": config.run_time.strftime("%H:%M"),
            "is_enabled": config.is_enabled,
            "next_run_at": next_run.isoformat() if config.is_enabled else None,
        }

    def _parse_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        if value in {0, 1}:
            return bool(value)
        return None

    # ----------------------------------------------------------
    # QUERYSET FILTERS
    # ----------------------------------------------------------

    def get_queryset(self):
        qs = super().get_queryset()

        params = self.request.query_params
        trip_date = params.get("date") or params.get("trip_date")
        today_flag = params.get("today")
        panchayat = params.get("panchayat_id")
        ward = params.get("ward_id")
        zone = params.get("zone_id")
        trip_plan = params.get("trip_plan_id")
        trip_status = params.get("status")
        waste_type = params.get("waste_type_id")
        mine = params.get("mine")

        mine_requested = mine and str(mine).lower() in ("1", "true", "yes")

        if mine_requested or self._is_supervisor_user():
            # Assignments whose trip plan this supervisor owns
            # (TripPlan.supervisor_id == requester). Auto-enforced for any
            # supervisor role on the admin web app too, not just when the
            # mobile app explicitly passes mine=true.
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan
            supervised_plan_ids = TripPlan.objects.filter(
                supervisor_id=self.request.user.staff_unique_id,
            ).values_list("unique_id", flat=True)
            qs = qs.filter(trip_plan_id__in=supervised_plan_ids)

        # Workbench date comes from the server, including for devices left open
        # overnight. Explicit modes preserve the existing desktop list contract.
        mode = params.get("trip_view")
        if mode and mode not in {"workbench", "history"}:
            raise ValidationError({"trip_view": "Use workbench or history."})
        self.trip_as_of = timezone.localtime()
        service_date = self.trip_as_of.date()
        closed = [DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED]
        if mode == "workbench":
            qs = qs.filter(Q(trip_date=service_date) | (Q(trip_date__lt=service_date) & ~Q(status__in=closed)))
        elif mode == "history":
            qs = qs.filter(status__in=closed)
            # Initial history window is seven service dates, newest first.
            if not params.get("from_date") and not params.get("to_date"):
                qs = qs.filter(trip_date__range=(service_date - timedelta(days=6), service_date))
            qs = qs.order_by("-trip_date", "-created_at", "-unique_id")

        dates = {}
        for key in ("from_date", "to_date"):
            if params.get(key):
                try:
                    dates[key] = datetime.strptime(params[key], "%Y-%m-%d").date()
                except (TypeError, ValueError):
                    raise ValidationError({key: "Use YYYY-MM-DD."})
        if dates.get("from_date") and dates.get("to_date") and dates["from_date"] > dates["to_date"]:
            raise ValidationError({"to_date": "Must be on or after from_date."})
        if "from_date" in dates:
            qs = qs.filter(trip_date__gte=dates["from_date"])
        if "to_date" in dates:
            qs = qs.filter(trip_date__lte=dates["to_date"])
        if params.get("retrip_only") == "true":
            qs = qs.filter(
                unique_id__in=TripRetripRequest.objects.filter(
                    is_deleted=False, new_assignment_id__isnull=False
                ).values("new_assignment_id")
            )
        if params.get("exceptions_only") == "true":
            from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
            from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
            from app.models.core_modules.daily_operations.daily_trip_household_collection import DailyTripHouseholdCollection
            from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown

            retrip_assignment_ids = set(
                TripRetripRequest.objects.filter(is_deleted=False).values_list("assignment_id", flat=True)
            )
            delay_assignment_ids = set(
                TripDelayReport.objects.filter(is_deleted=False).values_list("trip_assignment_id", flat=True)
            )
            unresolved_cp_assignment_ids = set(
                DailyTripCollectionPoint.objects.filter(is_deleted=False)
                .exclude(status__in=["Pending", "In Progress", "Collected"])
                .values_list("trip_assignment_id", flat=True)
            )
            unresolved_household_assignment_ids = set(
                DailyTripHouseholdCollection.objects.filter(is_deleted=False)
                .exclude(status__in=["Pending", "Collected"])
                .values_list("trip_assignment_id", flat=True)
            )
            breakdown_assignment_ids = set(
                VehicleBreakdown.objects.filter(is_deleted=False).values_list("trip_assignment_id", flat=True)
            )
            exception_ids = (
                retrip_assignment_ids
                | delay_assignment_ids
                | unresolved_cp_assignment_ids
                | unresolved_household_assignment_ids
                | breakdown_assignment_ids
            )
            qs = qs.filter(unique_id__in=exception_ids)

        if trip_date:
            qs = qs.filter(trip_date=trip_date)

        if today_flag and str(today_flag).lower() in ("1", "true", "yes"):
            qs = qs.filter(trip_date=timezone.localdate())

        if panchayat:
            qs = qs.filter(panchayat_id=panchayat)

        if ward:
            qs = qs.filter(ward_ids__contains=ward)

        if zone:
            from app.models.masters.ward import Ward
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan

            ward_ids_in_zone = set(
                Ward.objects.filter(zone_id=zone).values_list("unique_id", flat=True)
            )
            plan_ids_in_zone = set(
                TripPlan.objects.filter(zone_id=zone).values_list("unique_id", flat=True)
            )
            plan_ids_with_zone_ward = {
                plan.unique_id
                for plan in TripPlan.objects.exclude(ward_ids="")
                if ward_ids_in_zone & set(plan.get_ward_ids())
            }
            matching_ids = {
                assignment.unique_id
                for assignment in qs
                if (ward_ids_in_zone & set(assignment.get_ward_ids()))
                or assignment.trip_plan_id in plan_ids_in_zone
                or assignment.trip_plan_id in plan_ids_with_zone_ward
            }
            qs = qs.filter(unique_id__in=matching_ids)

        if trip_plan:
            qs = qs.filter(trip_plan_id=trip_plan)

        if trip_status:
            qs = qs.filter(status=trip_status)

        if waste_type:
            qs = qs.filter(waste_type_ids__contains=waste_type)

        search = params.get("search")
        if search:
            qs = self._apply_search(qs, search)

        return qs

    def _apply_search(self, qs, search):
        """Python-side replacement for DRF's SearchFilter: every field it
        used to search is now a plain id column, not a joinable relation."""
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
        from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        from app.models.masters.panchayat import Panchayat
        from app.models.masters.ward import Ward
        from app.models.masters.zone import Zone
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        needle = search.strip().lower()
        if not needle:
            return qs

        assignments = list(qs)
        plan_ids = {a.trip_plan_id for a in assignments if a.trip_plan_id}
        plans_by_id = {p.unique_id: p for p in TripPlan.objects.filter(unique_id__in=plan_ids)}

        staff_template_ids = {a.staff_template_id for a in assignments if a.staff_template_id}
        staff_templates_by_id = {
            st.unique_id: st for st in StaffTemplate.objects.filter(unique_id__in=staff_template_ids)
        }
        alt_template_ids = {a.alt_staff_template_id for a in assignments if a.alt_staff_template_id}
        alt_templates_by_id = {
            at.unique_id: at for at in AlternativeStaffTemplate.objects.filter(unique_id__in=alt_template_ids)
        }

        driver_ids = {t.driver_id for t in staff_templates_by_id.values() if t.driver_id}
        driver_ids |= {t.driver_id for t in alt_templates_by_id.values() if t.driver_id}
        drivers_by_id = {
            d.staff_unique_id: d for d in Staffcreation.objects.filter(staff_unique_id__in=driver_ids)
        }

        vehicle_ids = {a.vehicle_id for a in assignments if a.vehicle_id}
        vehicles_by_id = {v.unique_id: v for v in VehicleCreation.objects.filter(unique_id__in=vehicle_ids)}

        panchayat_ids = {a.panchayat_id for a in assignments if a.panchayat_id}
        panchayats_by_id = {p.unique_id: p for p in Panchayat.objects.filter(unique_id__in=panchayat_ids)}

        all_ward_ids = set()
        for a in assignments:
            all_ward_ids.update(a.get_ward_ids())
        wards_by_id = {w.unique_id: w for w in Ward.objects.filter(unique_id__in=all_ward_ids)}

        zone_ids = {p.zone_id for p in plans_by_id.values() if p.zone_id}
        zones_by_id = {z.unique_id: z for z in Zone.objects.filter(unique_id__in=zone_ids)}

        def matches(assignment):
            haystacks = [assignment.unique_id]
            plan = plans_by_id.get(assignment.trip_plan_id)
            if plan:
                haystacks.append(plan.display_code)
                zone = zones_by_id.get(plan.zone_id)
                if zone:
                    haystacks.append(zone.zone_name)
            vehicle = vehicles_by_id.get(assignment.vehicle_id)
            if vehicle:
                haystacks.append(vehicle.vehicle_no)
            for template in (
                staff_templates_by_id.get(assignment.staff_template_id),
                alt_templates_by_id.get(assignment.alt_staff_template_id),
            ):
                driver = drivers_by_id.get(getattr(template, "driver_id", None))
                if driver:
                    haystacks.append(driver.employee_name)
            panchayat = panchayats_by_id.get(assignment.panchayat_id)
            if panchayat:
                haystacks.append(panchayat.panchayat_name)
            for ward_id in assignment.get_ward_ids():
                ward = wards_by_id.get(ward_id)
                if ward:
                    haystacks.append(ward.ward_name)
            return any(needle in str(value).lower() for value in haystacks if value)

        matching_ids = [a.unique_id for a in assignments if matches(a)]
        return qs.filter(unique_id__in=matching_ids)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if request.query_params.get("trip_view"):
            as_of = getattr(self, "trip_as_of", timezone.localtime())
            if isinstance(response.data, list):
                response.data = {"results": response.data, "next": None, "count": len(response.data)}
            response.data["service_date"] = as_of.date().isoformat()
            response.data["as_of"] = as_of.isoformat()
        return response

    # ----------------------------------------------------------
    # UPDATE — cancelled trips remain locked, other daily trips can be edited
    # ----------------------------------------------------------

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.status == DailyTripAssignment.STATUS_CANCELLED:
            return Response(
                {"detail": "Cancelled assignments cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="scheduler-status")
    def scheduler_status(self, request):
        data = get_scheduler_status()
        config = SchedulerConfig.get_singleton()
        data.update(self._scheduler_config_payload(config))
        data["enabled"] = config.is_enabled
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get", "patch"], url_path="scheduler-config")
    def scheduler_config(self, request):
        config = SchedulerConfig.get_singleton()
        if request.method == "GET":
            return Response(
                self._scheduler_config_payload(config),
                status=status.HTTP_200_OK,
            )
        run_time_str = request.data.get("run_time")
        is_enabled = request.data.get("is_enabled")
        if run_time_str is not None:
            try:
                hour, minute = str(run_time_str).split(":", 1)
                parsed_hour = int(hour)
                parsed_minute = int(minute)
                if not (0 <= parsed_hour <= 23 and 0 <= parsed_minute <= 59):
                    raise ValueError
                config.run_time = datetime_time(parsed_hour, parsed_minute)
            except (ValueError, TypeError):
                return Response(
                    {"run_time": "Use HH:MM 24-hour format (e.g. 00:00, 04:00, 12:30)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if is_enabled is not None:
            parsed_enabled = self._parse_bool(is_enabled)
            if parsed_enabled is None:
                return Response(
                    {"is_enabled": "Use true or false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            config.is_enabled = parsed_enabled
        config.save()
        notify_scheduler_config_changed()
        return Response(
            self._scheduler_config_payload(config),
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="run-scheduler")
    def run_scheduler(self, request):
        raw_date = request.data.get("date")
        target_date = None
        if raw_date:
            try:
                target_date = timezone.datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"date": "Use YYYY-MM-DD format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        result = run_daily_trip_job(target_date=target_date, force=True)
        return Response(result, status=status.HTTP_200_OK)

    # ----------------------------------------------------------
    # ACTION: MANUAL JOB-SCHEDULER RUN  (for testing / on-demand)
    # POST /daily-trip-assignments/generate-daily/
    # body: { "date": "YYYY-MM-DD" }   (optional, defaults to today)
    # ----------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="generate-daily")
    def generate_daily(self, request):
        """Manually run the daily trip auto-assign job for one date.

        Mirrors the nightly/background scheduler
        (app.services.daily_trip_scheduler.run_daily_trip_job) so admins can
        generate / back-fill a day's trips on demand without shell access.
        Idempotent — re-running the same date creates no duplicates.
        """
        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can run the daily scheduler."},
                status=status.HTTP_403_FORBIDDEN,
            )

        target_date = None
        raw_date = request.data.get("date")
        if raw_date:
            try:
                target_date = timezone.datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        summary = run_for_date(target_date=target_date)

        return Response(
            {
                "message": (
                    f"Generated {summary['created']} assignment(s); "
                    f"skipped {summary['skipped']} plan(s) for {summary['date']}."
                ),
                **summary,
            },
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # DELETE — soft-delete + cancel
    # ----------------------------------------------------------

    def perform_destroy(self, instance):
        previous_data = self._serialize_instance(instance)

        instance.is_deleted = True
        instance.is_active = False
        instance.status = DailyTripAssignment.STATUS_CANCELLED
        instance.save(update_fields=["is_deleted", "is_active", "status", "updated_at"])

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

    # ----------------------------------------------------------
    # ACTION: STATUS TRANSITION
    # PATCH /trip-assignments/{unique_id}/status/
    # ----------------------------------------------------------

    @action(detail=True, methods=["patch"], url_path="status")
    @transaction.atomic
    def update_status(self, request, unique_id=None):
        instance = self.get_object()
        instance = DailyTripAssignment.objects.select_for_update().get(pk=instance.pk)
        expected = request.data.get("expected_status")
        if expected and instance.status != expected:
            return Response({"detail": "This trip has changed. Refresh before taking action."}, status=409)

        serializer = DailyTripAssignmentStatusSerializer(
            data=request.data,
            context={"instance": instance, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]
        previous_data = self._serialize_instance(instance)
        reason = str(request.data.get("reason") or "").strip()
        if reason:
            instance.remarks = "\n".join(filter(None, [instance.remarks, f"{new_status}: {reason}"]))
            instance.save(update_fields=["remarks", "updated_at"])

        if new_status == DailyTripAssignment.STATUS_IN_PROGRESS:
            instance.mark_started()
        elif new_status == DailyTripAssignment.STATUS_COMPLETED:
            instance.mark_ended()
        else:
            instance.status = new_status
            instance.save()

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            DailyTripAssignmentSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # ACTION: APPROVAL TRANSITION
    # PATCH /trip-assignments/{unique_id}/approval/
    # ----------------------------------------------------------

    @action(detail=True, methods=["patch"], url_path="approval")
    def update_approval(self, request, unique_id=None):
        instance = self.get_object()

        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can approve or reject assignments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DailyTripAssignmentApprovalSerializer(
            data=request.data,
            context={"instance": instance, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        previous_data = self._serialize_instance(instance)
        instance.approval_status = serializer.validated_data["approval_status"]
        reason = str(request.data.get("reason") or "").strip()
        if reason:
            instance.remarks = "\n".join(filter(None, [instance.remarks, f"Assignment {instance.approval_status.lower()}: {reason}"]))
        instance.save(update_fields=["approval_status", "remarks", "updated_at"])

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            DailyTripAssignmentSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # ACTION: RE-TRIP — close this trip early, open a continuation
    # POST /trip-assignments/{unique_id}/proceed-next-trip/
    # body: { collection_point_ids?: string[], remarks: string }
    # ----------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="proceed-next-trip")
    def proceed_next_trip(self, request, unique_id=None):
        """Supervisor/admin closes this trip from the web and opens a
        continuation for the leftover stops — e.g. the truck is full and
        going for weighment. One-step web equivalent of a driver-raises/
        supervisor-approves Re-Trip flow (see
        app.services.retrip_service.proceed_to_next_trip).
        """
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        from app.services import retrip_service

        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can proceed to a next trip."},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance = self.get_object()

        remarks = (request.data.get("remarks") or "").strip()
        if not remarks:
            return Response(
                {"remarks": "Remarks are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_ids = request.data.get("collection_point_ids")
        collection_point_ids = None
        if raw_ids is not None:
            if not isinstance(raw_ids, (list, tuple)):
                return Response(
                    {"collection_point_ids": "Expected a list of stop ids."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            collection_point_ids = [str(value) for value in raw_ids]

        # A trip is either a bin trip or a household trip (never both) — bin
        # trips require an explicit pick; household trips always carry
        # everything.
        is_bin_trip = instance.trip_collection_points.exists()
        if is_bin_trip and not collection_point_ids:
            return Response(
                {"collection_point_ids": "Select at least one collection point to carry over."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actor = request.user if isinstance(request.user, Staffcreation) else None

        try:
            retrip_request, continuation = retrip_service.proceed_to_next_trip(
                instance,
                actor=actor,
                collection_point_ids=collection_point_ids,
                remarks=remarks,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        instance.refresh_from_db()
        self.log_audit(
            request,
            instance=instance,
            previous_data=None,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            {
                "assignment": DailyTripAssignmentSerializer(instance, context={"request": request}).data,
                "new_assignment_id": continuation.unique_id,
                "retrip_request_id": retrip_request.unique_id,
            },
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _has_approval_role(self, request) -> bool:
        """Returns True if the requesting user holds supervisor or admin role."""
        user = getattr(request, "user", None)
        if not user:
            return False

        # Platform superadmin always has approval rights
        if getattr(user, "is_superuser", False) and getattr(user, "company_id", None) is None:
            return True

        role_obj = getattr(user, "staffusertype_id", None)
        role_name = getattr(role_obj, "name", "") or ""
        return role_name.lower() in ("supervisor", "admin", "company_admin")

    def perform_create(self, serializer):
        previous_data = None
        super().perform_create(serializer)
        instance = serializer.instance
        new_data = self._serialize_instance(instance)
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=new_data,
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
