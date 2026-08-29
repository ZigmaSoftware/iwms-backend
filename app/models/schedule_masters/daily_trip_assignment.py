from datetime import timedelta

from django.db import connection, models, transaction
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.user_creations.waste_collection_bluetooth import WasteType


def _generate_trip_assignment_unique_id(company_id, project_id):
    """
    Generates TRIP-YYYY-MM-NNN with a globally unique sequence for the month.
    The unique_id column has no per-company constraint, so the NNN counter must
    be global (not scoped per company+project) to avoid cross-tenant collisions.
    Uses select_for_update() to serialize concurrent inserts.
    """
    today = timezone.localdate()
    prefix = f"TRIP-{today.year}-{today.month:02d}"
    from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint

    with transaction.atomic():
        assignment_ids = (
            DailyTripAssignment.objects.select_for_update()
            .filter(unique_id__startswith=f"{prefix}-")
            .values_list("unique_id", flat=True)
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT DISTINCT trip_assignment_id
                FROM {DailyTripCollectionPoint._meta.db_table}
                WHERE trip_assignment_id LIKE %s
                """,
                [f"{prefix}-%"],
            )
            collection_point_assignment_ids = [row[0] for row in cursor.fetchall()]
        max_seq = 0
        for uid in set(assignment_ids).union(collection_point_assignment_ids):
            try:
                seq = int(uid.rsplit("-", 1)[-1])
                if seq > max_seq:
                    max_seq = seq
            except (ValueError, IndexError):
                pass
        return f"{prefix}-{max_seq + 1:03d}"


class DailyTripAssignment(BaseMaster):

    STATUS_SCHEDULED = "Scheduled"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    APPROVAL_PENDING = "Pending"
    APPROVAL_APPROVED = "Approved"
    APPROVAL_REJECTED = "Rejected"

    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    # ------------------------------------------------------------------
    # IDENTIFIER
    # ------------------------------------------------------------------

    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    # ------------------------------------------------------------------
    # TENANCY
    # ------------------------------------------------------------------

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="daily_trip_assignments",
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        related_name="daily_trip_assignments",
    )

    # ------------------------------------------------------------------
    # TRIP PLAN & STAFF
    # ------------------------------------------------------------------

    trip_plan_id = models.ForeignKey(
        TripPlan,
        on_delete=models.PROTECT,
        db_column="trip_plan_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    staff_template_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        db_column="staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    alt_staff_template_id = models.ForeignKey(
        AlternativeStaffTemplate,
        on_delete=models.PROTECT,
        db_column="alt_staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # LOCATION
    # ------------------------------------------------------------------

    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    wards = models.ManyToManyField(
        Ward,
        related_name="daily_trip_assignments_m2m",
        blank=True,
    )

    # ------------------------------------------------------------------
    # WASTE TYPE
    # ------------------------------------------------------------------

    waste_type_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of waste type unique_ids assigned to this daily trip plan.",
    )

    # Waste types collected on this daily trip (inherited from the Trip Plan;
    # can be narrowed per-trip). Mirrors TripPlan.waste_types.
    waste_types = models.ManyToManyField(
        WasteType,
        related_name="daily_trip_assignments_multi",
        blank=True,
    )

    # Multiple waste types for household collection stops on this trip
    household_waste_type_ids = models.ManyToManyField(
        WasteType,
        related_name="household_trip_assignments",
        blank=True,
    )

    # ------------------------------------------------------------------
    # VEHICLE (explicit for operator-mobile flow)
    # ------------------------------------------------------------------

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # SCHEDULING
    # ------------------------------------------------------------------

    trip_date = models.DateField()
    scheduled_time = models.TimeField()

    # Wall-clock times kept for backward compatibility — dashboards, the
    # DailyTripLog mirror and the mobile serializer all still read these. They
    # are DERIVED from the `_at` datetimes below; never stamp them directly,
    # use mark_started() / mark_ended().
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    # The authoritative timestamps. TimeField alone cannot express a trip that
    # crosses midnight (end < start reads as a negative duration) and carries no
    # timezone — the viewset's update_status action used to stamp
    # `timezone.now().time()` (UTC) while other callers used `localtime()`
    # (IST), so the same column held values 5h30m apart depending on the caller.
    actual_start_at = models.DateTimeField(null=True, blank=True, db_index=True)
    actual_end_at = models.DateTimeField(null=True, blank=True)

    # ------------------------------------------------------------------
    # STATUS & APPROVAL
    # ------------------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        db_index=True,
    )

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_PENDING,
        db_index=True,
    )

    remarks = models.TextField(null=True, blank=True)

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ------------------------------------------------------------------
    # META
    # ------------------------------------------------------------------

    class Meta:
        ordering = ["-trip_date", "-scheduled_time"]
        indexes = [
            models.Index(fields=["trip_date", "status"]),
            models.Index(fields=["trip_plan_id", "trip_date"]),
            models.Index(fields=["panchayat_id", "trip_date"]),
        ]
        # No uniqueness on (trip_plan_id, trip_date): a Re-Trip continuation
        # (see app/services/retrip_service.py) is deliberately a second
        # assignment on the SAME plan and date as the source it closes out,
        # carrying the leftover stops. A DB-level UniqueConstraint here
        # (removed in migration 0006) made every Re-Trip approval crash with
        # an IntegrityError — mirrors government's schema, which never had
        # this constraint. Callers that fetch "the" assignment for a
        # (plan, date) must not assume at most one row exists — see
        # RetripDemoSeeder._get_or_create_today_assignment and
        # generate_assignment_for_plan for the safe pattern.

    # ------------------------------------------------------------------
    # UNIQUE_ID GENERATION
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        if self.trip_plan_id:
            # Accessing an unset non-nullable FK descriptor on an unsaved
            # instance raises RelatedObjectDoesNotExist rather than
            # returning None, so check the raw FK id first (works whether
            # the field was left unset entirely or explicitly set to None).
            if not self.staff_template_id_id:
                self.staff_template_id = self.trip_plan_id.staff_template_id
            if not self.vehicle_id_id:
                self.vehicle_id = self.trip_plan_id.vehicle_id
            if not self.panchayat_id_id:
                self.panchayat_id = self.trip_plan_id.panchayat_id
            self.scheduled_time = self.scheduled_time or self.trip_plan_id.scheduled_time
            self.waste_type_ids = self.waste_type_ids or self.trip_plan_id.waste_type_ids
        is_new = self._state.adding
        if not self.unique_id:
            with transaction.atomic():
                self.unique_id = _generate_trip_assignment_unique_id(
                    self.company_id, self.project_id
                )
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

        if is_new and self.trip_plan_id:
            if not self.waste_types.exists():
                self.waste_types.set(self.trip_plan_id.waste_types.all())
            if not self.wards.exists():
                self.wards.set(self.trip_plan_id.wards.all())
                # post_save fires before M2M wards are available on this
                # instance, so household/bulk stops (which are narrowed to
                # the assignment's wards) may have been under-matched on the
                # first cloning pass. Re-sync once more now that wards are
                # copied — idempotent, mirrors TN_Iwms.
                from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan
                sync_daily_assignment_stops_from_plan(self)

    def __str__(self):
        return self.unique_id

    @property
    def primary_waste_type(self):
        if not self.waste_type_ids:
            return None
        return WasteType.objects.filter(
            unique_id=self.waste_type_ids[0],
            is_deleted=False,
        ).first()

    def pending_bin_stops(self):
        """Bin collection points still awaiting the driver."""
        from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint

        return self.trip_collection_points.filter(is_deleted=False).exclude(
            status__in=(
                DailyTripCollectionPoint.STATUS_COLLECTED,
                DailyTripCollectionPoint.STATUS_MISSED,
            )
        )

    def pending_household_stops(self):
        """Household stops still awaiting the driver."""
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        return self.trip_household_collections.filter(is_deleted=False).exclude(
            status__in=(
                DailyTripHouseholdCollection.STATUS_COLLECTED,
                DailyTripHouseholdCollection.STATUS_MISSED,
            )
        )

    def has_pending_stops(self):
        return self.pending_bin_stops().exists() or self.pending_household_stops().exists()

    def mark_started(self, at=None):
        """Put the trip In Progress and stamp the start timestamps.

        Idempotent: calling it on an already-started trip is a no-op, so the
        explicit driver action and the implicit first-scan path can both call
        it without fighting over the timestamp. Also backfills a start time
        for a trip that was forced In Progress without one (e.g. the vehicle
        breakdown replacement path).
        """
        if self.status in (self.STATUS_COMPLETED, self.STATUS_CANCELLED):
            return False

        started_at = at or timezone.localtime()
        update_fields = ["updated_at"]

        if self.status != self.STATUS_IN_PROGRESS:
            self.status = self.STATUS_IN_PROGRESS
            update_fields.append("status")

        if not self.actual_start_at:
            self.actual_start_at = started_at
            self.actual_start_time = timezone.localtime(started_at).time()
            update_fields += ["actual_start_at", "actual_start_time"]

        if len(update_fields) == 1:  # nothing but updated_at — already started
            return False

        self.save(update_fields=update_fields)
        return True

    def mark_ended(self, at=None):
        """Close the trip and stamp the end timestamps. Idempotent."""
        if self.status == self.STATUS_COMPLETED:
            return False

        ended_at = at or timezone.localtime()
        update_fields = ["status", "updated_at"]
        self.status = self.STATUS_COMPLETED

        if not self.actual_end_at:
            self.actual_end_at = ended_at
            self.actual_end_time = timezone.localtime(ended_at).time()
            update_fields += ["actual_end_at", "actual_end_time"]

        # A trip can be completed without ever having been explicitly started
        # (all work done through scans before this feature existed). Backfill
        # so duration math never sees a null start against a real end.
        if not self.actual_start_at:
            self.actual_start_at = ended_at
            self.actual_start_time = timezone.localtime(ended_at).time()
            update_fields += ["actual_start_at", "actual_start_time"]

        self.save(update_fields=update_fields)
        return True

    @property
    def total_trip_time(self):
        """Wall-clock duration from `actual_start_at` to `actual_end_at`, or to
        now while still In Progress. `None` until the trip has been started —
        never derived from the legacy `actual_start_time`/`actual_end_time`
        TimeFields, which carry no date and (historically) mixed timezones.
        """
        if not self.actual_start_at:
            return None
        end = self.actual_end_at or timezone.localtime()
        diff = end - self.actual_start_at
        return diff if diff.total_seconds() >= 0 else timedelta(0)

    def trip_count(self):
        """This assignment's 1-based position among all assignments made
        today for the same trip plan — the ordinary run is `1`; a Re-Trip
        continuation (`app/services/retrip_service.py`, same `trip_plan_id`
        and `trip_date`, a fresh row with no direct FK back to its source)
        is `2`, and so on for a chain of same-day re-trips. Ordered by
        `created_at` so the count reflects the order the shifts actually
        happened in, not unique_id string order. Ported from the
        government backend's identically-named/-behaved method.
        """
        siblings = list(
            DailyTripAssignment.objects.filter(
                trip_plan_id=self.trip_plan_id,
                trip_date=self.trip_date,
                is_deleted=False,
            )
            .order_by("created_at", "unique_id")
            .values_list("unique_id", flat=True)
        )
        try:
            return siblings.index(self.unique_id) + 1
        except ValueError:
            # Not persisted yet (unsaved instance) — it would be the next one.
            return len(siblings) + 1

    def mark_completed_if_all_cps_collected(self):
        children = self.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return False
        # A missed stop is operationally resolved for the day but contributes
        # zero weight. "Skipped"/collect-later remains unresolved. Mirrors
        # TN_Iwms's DailyTripAssignment.mark_completed_if_all_cps_collected.
        from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
        if children.exclude(
            status__in=[
                DailyTripCollectionPoint.STATUS_COLLECTED,
                DailyTripCollectionPoint.STATUS_MISSED,
            ]
        ).exists():
            return False
        if self.status == self.STATUS_COMPLETED:
            return True

        self.mark_ended()
        return True

    def mark_completed_if_all_household_stops_collected(self):
        """Household-collection counterpart to
        `mark_completed_if_all_cps_collected` — that method only ever looks at
        `trip_collection_points` (bin stops), so it always bails out
        (`children.exists()` is False) for a pure household trip, and a
        household assignment could never auto-complete: every stop showing
        Collected/Not Available on the driver's Households list, but the trip
        card still reading "IN PROGRESS" forever.

        Same idempotent "declare done, then mark_ended()" shape as the bin
        version, using `pending_household_stops()` (already excludes
        Collected/Not Available, i.e. Collect Later remains unresolved) so the
        "what counts as resolved" rule for households matches the bin one.
        """
        children = self.trip_household_collections.filter(is_deleted=False)
        if not children.exists():
            return False
        if self.pending_household_stops().exists():
            return False
        if self.status == self.STATUS_COMPLETED:
            return True

        self.mark_ended()
        return True
