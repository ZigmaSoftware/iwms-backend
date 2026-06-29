"""Seed ONE canonical shared trip for the driver_user / operator_user pair.

This is a deterministic demo fixture proving the centralized trip flow: a single
``DailyTripAssignment`` lives on the staff template that pairs ``driver_user``
(driver) with ``operator_user`` (operator). Because the trip hangs off the
*template* — not off either individual — the operator-mobile resolver
(``find_active_assignment_for_operator``) and the driver-mobile resolver
(``find_active_assignment_for_driver``) both land on this same row. When the
operator marks a collection point collected, the driver reads the very same
``DailyTripCollectionPoint`` records, so progress updates are shared instantly.

The seeder is idempotent and self-healing for *today*:
  * reuses today's trip on this template if one already exists (picking the
    earliest scheduled one so it matches the resolvers' deterministic order),
  * otherwise creates a fresh trip from one of the template's approved plans,
  * (re)builds the trip's collection points and resets them to PENDING so a
    re-run always yields a clean, uncollected, demo-ready trip.

Runs after DailyTripCollectionPointSeeder so its CP reset is the final word.
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.user_creations.staffcreation import Staffcreation

DRIVER_USERNAME = "driver_user"
OPERATOR_USERNAME = "operator_user"


class SharedDemoTripSeeder(BaseSeeder):
    name = "shared_demo_trip"

    def _resolve_staff(self, username):
        return (
            Staffcreation.objects
            .filter(username__iexact=username, is_active=True, is_deleted=False)
            .order_by("staff_unique_id")
            .first()
        )

    def _ward_ids(self, obj):
        return list(obj.wards.values_list("unique_id", flat=True))

    def _has_area(self, obj):
        return bool(obj.panchayat_id_id or self._ward_ids(obj))

    def run(self):
        today = timezone.localdate()

        driver = self._resolve_staff(DRIVER_USERNAME)
        operator = self._resolve_staff(OPERATOR_USERNAME)
        if not driver or not operator:
            self.log(
                f"Missing staff (driver={bool(driver)}, operator={bool(operator)}) "
                "— run user-creations seeders first. Aborting."
            )
            return

        template = (
            StaffTemplate.objects
            .filter(
                driver_id=driver,
                operator_id=operator,
                is_deleted=False,
                status="ACTIVE",
                approval_status="APPROVED",
            )
            .order_by("unique_id")
            .first()
        )
        if not template:
            self.log(
                "No ACTIVE/APPROVED StaffTemplate pairs driver_user + operator_user "
                "— run StaffTemplateSeeder first. Aborting."
            )
            return

        # Reuse today's trip on this template if present, picking the earliest
        # scheduled one so we match the resolvers' (scheduled_time, unique_id)
        # order — i.e. the exact row both mobile apps will fetch.
        assignment = (
            DailyTripAssignment.objects
            .filter(
                staff_template_id=template,
                trip_date=today,
                is_deleted=False,
            )
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related("company_id", "project_id", "panchayat_id", "vehicle_id")
            .prefetch_related("wards")
            .order_by("scheduled_time", "unique_id")
            .first()
        )

        if assignment is None:
            plan = (
                TripPlan.objects
                .filter(
                    staff_template_id=template,
                    is_deleted=False,
                    status=TripPlan.Status.ACTIVE,
                    approval_status=TripPlan.ApprovalStatus.APPROVED,
                )
                .select_related("company_id", "project_id", "panchayat_id", "waste_type_id", "vehicle_id")
                .prefetch_related("wards")
                .order_by("scheduled_time", "unique_id")
                .first()
            )
            if plan is None or not self._has_area(plan):
                self.log(
                    "No usable approved TripPlan on this template (need one with a "
                    "panchayat or ward) — run TripPlanSeeder first. Aborting."
                )
                return

            # model.save() inherits staff_template/vehicle/waste_type/area/time
            # from the plan, so we only pass what's needed.
            assignment = DailyTripAssignment.objects.create(
                company_id=plan.company_id,
                project_id=plan.project_id,
                trip_plan_id=plan,
                staff_template_id=template,
                panchayat_id=plan.panchayat_id,
                waste_type_ids=plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else []),
                vehicle_id=plan.vehicle_id,
                trip_date=today,
                scheduled_time=plan.scheduled_time,
                status=DailyTripAssignment.STATUS_IN_PROGRESS,
                approval_status=DailyTripAssignment.APPROVAL_APPROVED,
            )
            assignment.wards.set(plan.wards.all())
            self.log(f"Created shared trip {assignment.unique_id} on {template.display_code}.")
        else:
            self.log(
                f"Reusing today's shared trip {assignment.unique_id} on "
                f"{template.display_code}."
            )

        created, reset = self._rebuild_collection_points(assignment, today)

        # Wipe any prior collection events and re-open the trip so the demo
        # always starts from a clean, in-progress, fully-uncollected state.
        BinCollectionEvent.objects.filter(
            trip_assignment_id=assignment, is_deleted=False
        ).update(is_deleted=True)
        if assignment.status != DailyTripAssignment.STATUS_IN_PROGRESS:
            assignment.status = DailyTripAssignment.STATUS_IN_PROGRESS
            assignment.actual_end_time = None
            assignment.save(update_fields=["status", "actual_end_time", "updated_at"])

        # A second, *completed* trip on the SAME paired template so the operator
        # and driver share identical history (not just the active trip). Both
        # resolvers match on the template, so this completed trip surfaces in
        # both mobile apps' History tab.
        completed = self._ensure_completed_trip(template, assignment, operator, today)

        self.log(
            f"---SharedDemoTrip ready | active={assignment.unique_id} | "
            f"completed={completed.unique_id if completed else 'none'} | "
            f"template={template.display_code} | driver={DRIVER_USERNAME} | "
            f"operator={OPERATOR_USERNAME} | cps_created={created} | cps_reset={reset}---"
        )

    def _ensure_completed_trip(self, template, active_assignment, operator, today):
        """Create/reuse a COMPLETED shared trip on the paired template.

        Uses a different approved plan than the active trip (a distinct area) so
        the two trips don't collide on the same collection points. Idempotent:
        reuses today's completed trip on this template if one already exists.
        """
        existing = (
            DailyTripAssignment.objects
            .filter(
                staff_template_id=template,
                trip_date=today,
                status=DailyTripAssignment.STATUS_COMPLETED,
                is_deleted=False,
            )
            .select_related("company_id", "project_id", "panchayat_id", "vehicle_id")
            .prefetch_related("wards")
            .order_by("scheduled_time", "unique_id")
            .first()
        )

        if existing is None:
            existing = (
                DailyTripAssignment.objects
                .filter(
                    staff_template_id=template,
                    trip_date=today,
                    is_deleted=False,
                )
                .exclude(unique_id=active_assignment.unique_id)
                .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
                .select_related("company_id", "project_id", "panchayat_id", "vehicle_id")
                .prefetch_related("wards")
                .order_by("scheduled_time", "unique_id")
                .first()
            )

        if existing is None:
            # Pick an approved plan whose area differs from the active trip's, so
            # the completed trip is a genuinely distinct route.
            plan = (
                TripPlan.objects
                .filter(
                    staff_template_id=template,
                    is_deleted=False,
                    status=TripPlan.Status.ACTIVE,
                    approval_status=TripPlan.ApprovalStatus.APPROVED,
                )
                .exclude(unique_id=active_assignment.trip_plan_id_id)
                .exclude(daily_trip_assignments__trip_date=today)
                .select_related("company_id", "project_id", "panchayat_id", "waste_type_id", "vehicle_id")
                .prefetch_related("wards")
                .order_by("scheduled_time", "unique_id")
                .first()
            )
            if plan is None or not self._has_area(plan):
                self.log(
                    "No second approved TripPlan (distinct area) on this template "
                    "— skipping shared completed trip."
                )
                return None

            existing = DailyTripAssignment.objects.create(
                company_id=plan.company_id,
                project_id=plan.project_id,
                trip_plan_id=plan,
                staff_template_id=template,
                panchayat_id=plan.panchayat_id,
                waste_type_ids=plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else []),
                vehicle_id=plan.vehicle_id,
                trip_date=today,
                scheduled_time=plan.scheduled_time,
                status=DailyTripAssignment.STATUS_IN_PROGRESS,
                approval_status=DailyTripAssignment.APPROVAL_APPROVED,
            )
            existing.wards.set(plan.wards.all())
            self.log(
                f"Created shared completed trip {existing.unique_id} on "
                f"{template.display_code}."
            )

        self._rebuild_collection_points(existing, today)
        self._mark_trip_completed(existing, operator)
        return existing

    def _mark_trip_completed(self, assignment, operator):
        """Mark every CP collected and the trip completed (idempotent)."""
        now = timezone.now()
        cps = list(
            DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            )
        )
        for cp in cps:
            if cp.is_collected and cp.status == DailyTripCollectionPoint.STATUS_COLLECTED:
                continue
            cp.is_collected = True
            cp.status = DailyTripCollectionPoint.STATUS_COLLECTED
            cp.collected_at = now
            cp.collected_by = operator
            if cp.collected_weight_kg is None:
                cp.collected_weight_kg = 0
            cp.save(
                update_fields=[
                    "is_collected",
                    "status",
                    "collected_at",
                    "collected_by",
                    "collected_weight_kg",
                    "updated_at",
                ]
            )

        if (
            assignment.status != DailyTripAssignment.STATUS_COMPLETED
            or assignment.actual_end_time is None
        ):
            assignment.status = DailyTripAssignment.STATUS_COMPLETED
            if assignment.actual_start_time is None:
                assignment.actual_start_time = assignment.scheduled_time
            assignment.actual_end_time = now.time()
            assignment.save(
                update_fields=[
                    "status",
                    "actual_start_time",
                    "actual_end_time",
                    "updated_at",
                ]
            )

    def _rebuild_collection_points(self, assignment, today):
        """Ensure the trip has CPs and that every one is PENDING/uncollected."""
        cp_qs = Collection_point.objects.filter(
            company_id=assignment.company_id,
            project_id=assignment.project_id,
            is_deleted=False,
        )
        if assignment.panchayat_id:
            cp_qs = cp_qs.filter(panchayat_id=assignment.panchayat_id)
        else:
            ward_ids = self._ward_ids(assignment)
            if ward_ids:
                cp_qs = cp_qs.filter(wards__unique_id__in=ward_ids)
        cps = list(cp_qs.distinct().order_by("cp_name"))

        if not cps:
            cps = list(
                Collection_point.objects.filter(
                    company_id=assignment.company_id,
                    project_id=assignment.project_id,
                    is_deleted=False,
                ).order_by("cp_name")[:5]
            )

        created = reset = 0
        sequence = 0
        for cp in cps:
            bin_obj = (
                Bins.objects.filter(
                    collection_point_id=cp,
                    wastetype_id__unique_id__in=assignment.waste_type_ids,
                    is_deleted=False,
                ).first()
                or Bins.objects.filter(
                    collection_point_id=cp, is_deleted=False
                ).first()
            )
            if not bin_obj:
                continue
            sequence += 1
            trip_cp, was_created = DailyTripCollectionPoint.objects.get_or_create(
                trip_assignment_id=assignment,
                collection_point_id=cp,
                defaults={
                    "bin_id": bin_obj,
                    "sequence": sequence,
                    "is_collected": False,
                    "status": DailyTripCollectionPoint.STATUS_PENDING,
                },
            )
            if was_created:
                created += 1
            elif (
                trip_cp.is_collected
                or trip_cp.status != DailyTripCollectionPoint.STATUS_PENDING
                or trip_cp.collected_at is not None
                or trip_cp.collected_weight_kg is not None
                or trip_cp.collected_by_id is not None
            ):
                trip_cp.is_collected = False
                trip_cp.status = DailyTripCollectionPoint.STATUS_PENDING
                trip_cp.collected_at = None
                trip_cp.collected_weight_kg = None
                trip_cp.collected_by = None
                trip_cp.save(
                    update_fields=[
                        "is_collected",
                        "status",
                        "collected_at",
                        "collected_weight_kg",
                        "collected_by",
                        "updated_at",
                    ]
                )
                reset += 1
        return created, reset
