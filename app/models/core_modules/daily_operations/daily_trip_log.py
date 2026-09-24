from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from app.utils.base_models import Account, BaseMaster


def _generate_daily_trip_log_unique_id(company_id, project_id):
    today = timezone.localdate()
    prefix = f"DTL-{today.year}-{today.month:02d}"
    with transaction.atomic():
        existing = (
            DailyTripLog.objects.select_for_update()
            .filter(unique_id__startswith=f"{prefix}-")
            .values_list("unique_id", flat=True)
        )
        max_seq = 0
        for uid in existing:
            try:
                seq = int(uid.rsplit("-", 1)[-1])
                if seq > max_seq:
                    max_seq = seq
            except (ValueError, IndexError):
                pass
        return f"{prefix}-{max_seq + 1:03d}"


class DailyTripLog(BaseMaster):
    LOG_STATUS_UNVERIFIED = "Unverified"
    LOG_STATUS_VERIFIED = "Verified"

    LOG_STATUS_CHOICES = [
        (LOG_STATUS_UNVERIFIED, "Unverified"),
        (LOG_STATUS_VERIFIED, "Verified"),
    ]

    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    trip_assignment_id = models.CharField(max_length=30, null=True, blank=True)

    staff_template_id = models.CharField(max_length=20, null=True, blank=True)
    alt_staff_template_id = models.CharField(max_length=50, null=True, blank=True)

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    collection_point_id = models.CharField(max_length=30, null=True, blank=True)
    waste_type_id = models.CharField(max_length=30, null=True, blank=True)

    trip_date = models.DateField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    driver_id = models.CharField(max_length=30, null=True, blank=True)
    operator_id = models.CharField(max_length=30, null=True, blank=True)
    # Store extra operator IDs as comma-separated string
    extra_operator_ids = models.TextField(blank=True, default="")

    collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Auto-computed as the sum of all BinCollectionEvent weights for this trip.",
    )
    household_collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Auto-computed as the sum of all WasteCollection totals linked to this trip.",
    )

    vehicle_id = models.CharField(max_length=30, null=True, blank=True)
    # Store bin IDs as comma-separated string
    bin_ids = models.TextField(blank=True, default="")

    remarks = models.TextField(null=True, blank=True)
    log_status = models.CharField(
        max_length=20,
        choices=LOG_STATUS_CHOICES,
        default=LOG_STATUS_UNVERIFIED,
        db_index=True,
    )

    verified_by = models.CharField(max_length=30, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("daily_trip_log_list", "daily_trip_log_detail")

    class Meta:
        ordering = ["-trip_date", "-created_at"]
        indexes = [
            models.Index(fields=["trip_date", "log_status"]),
            models.Index(fields=["company_id", "project_id", "trip_date"]),
        ]

    def __str__(self):
        return self.unique_id

    def get_extra_operator_ids(self):
        return [o for o in self.extra_operator_ids.split(",") if o]

    def get_bin_ids(self):
        return [b for b in self.bin_ids.split(",") if b]

    def _resolve_effective_staff_template(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        if not assignment:
            return None
        return assignment.alt_staff_template_id or assignment.staff_template_id

    def autofill_from_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        if not assignment:
            return

        self.company_id = assignment.company_id
        self.project_id = assignment.project_id
        self.panchayat_id = assignment.panchayat_id
        self.zone_id = getattr(assignment, "zone_id", None)

        # For ward-based trips, derive panchayat or zone from the first ward.
        if not self.panchayat_id and not self.zone_id:
            from app.models.masters.ward import Ward
            ward_ids = assignment.get_ward_ids()
            if ward_ids:
                first_ward = Ward.objects.filter(unique_id=ward_ids[0]).first()
                if first_ward:
                    if first_ward.panchayat_id:
                        self.panchayat_id = first_ward.panchayat_id
                    elif first_ward.zone_id:
                        self.zone_id = first_ward.zone_id
        
        if not self.collection_point_id:
            first_child = (
                assignment.trip_collection_points
                .filter(is_deleted=False)
                .order_by("sequence")
                .first()
            )
            if first_child:
                self.collection_point_id = first_child.collection_point_id
        self.waste_type_id = assignment.primary_waste_type
        self.trip_date = assignment.trip_date
        self.actual_start_time = self.actual_start_time or assignment.actual_start_time
        self.actual_end_time = self.actual_end_time or assignment.actual_end_time

        self.staff_template_id = assignment.staff_template_id
        self.alt_staff_template_id = assignment.alt_staff_template_id

        if assignment.alt_staff_template_id:
            from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
            tmpl = AlternativeStaffTemplate.objects.filter(unique_id=assignment.alt_staff_template_id).first()
        elif assignment.staff_template_id:
            from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
            tmpl = StaffTemplate.objects.filter(unique_id=assignment.staff_template_id).first()
        else:
            tmpl = None
        if tmpl:
            self.driver_id = tmpl.driver_id
            self.operator_id = tmpl.operator_id

        if getattr(assignment, "vehicle_id", None):
            self.vehicle_id = assignment.vehicle_id
        elif getattr(assignment, "trip_plan_id", None):
            from app.models.core_modules.schedule_setup.trip_plan import TripPlan
            tp = TripPlan.objects.filter(unique_id=assignment.trip_plan_id).first()
            if tp:
                self.vehicle_id = tp.vehicle_id

    def sync_from_household_collections(self):
        """Aggregate household waste weight from WasteCollection records for this trip.

        Mirrors sync_from_bin_collection_events() — only overrides when records exist
        so that manually-entered values are preserved when no WasteCollections are linked.
        """
        from app.models.core_modules.daily_operations.wastecollection import WasteCollection

        records = WasteCollection.objects.filter(
            trip_assignment_id=self.trip_assignment_id,
            is_deleted=False,
        )
        if not records.exists():
            return

        total = records.aggregate(total=Sum("total_quantity"))["total"]
        self.household_collected_weight_kg = Decimal(str(total or 0))
        DailyTripLog.objects.filter(pk=self.pk).update(
            household_collected_weight_kg=self.household_collected_weight_kg,
        )

    def sync_from_bin_collection_events(self):
        """Aggregate total collected weight from BinCollectionEvent records for this trip.

        Only overrides collected_weight_kg when bin-scan events actually exist.
        When no events are present the manually-entered value is preserved so that
        operators who enter weight directly (without bin scanning) are not silently
        zeroed out.
        """
        from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent

        events = BinCollectionEvent.objects.filter(
            trip_assignment_id=self.trip_assignment_id,
            is_deleted=False,
        )
        if not events.exists():
            # No bin-scan events — keep whatever was manually entered.
            return

        total = events.aggregate(total=Sum("collected_weight_kg"))["total"]
        self.collected_weight_kg = total or Decimal("0")
        DailyTripLog.objects.filter(pk=self.pk).update(
            collected_weight_kg=self.collected_weight_kg,
        )

    def clean(self):
        super().clean()

        if not self.trip_assignment_id:
            return

        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        if not assignment:
            return
        if assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise ValidationError("Cannot create a log for a cancelled trip.")

        # Weight fields stay live even after verification — collected_weight_kg/
        # household_collected_weight_kg must keep reflecting collection points
        # or WasteCollection rows recorded/updated afterwards. "Verified" is an
        # approval checkpoint on the trip, not a freeze on the actual weight
        # collected. Every other field remains read-only once verified.
        WEIGHT_ONLY_FIELDS = {"collected_weight_kg", "household_collected_weight_kg", "updated_at"}
        if self.pk:
            previous = DailyTripLog.objects.filter(pk=self.pk).first()
            if previous and previous.log_status == self.LOG_STATUS_VERIFIED:
                other_field_changed = any(
                    getattr(self, field.attname) != getattr(previous, field.attname)
                    for field in self._meta.fields
                    if field.attname not in WEIGHT_ONLY_FIELDS
                )
                if other_field_changed:
                    raise ValidationError("Verified trip logs are read-only.")

        if self.log_status == self.LOG_STATUS_VERIFIED:
            bin_weight = self.collected_weight_kg or Decimal("0")
            household_weight = self.household_collected_weight_kg or Decimal("0")
            if bin_weight <= 0 and household_weight <= 0:
                raise ValidationError(
                    "Either collected_weight_kg or household_collected_weight_kg must be "
                    "greater than 0 before verifying."
                )

    def save(self, *args, **kwargs):
        self.autofill_from_assignment()
        if not self.unique_id:
            with transaction.atomic():
                self.unique_id = _generate_daily_trip_log_unique_id(
                    self.company_id, self.project_id
                )
                self.full_clean()
                super().save(*args, **kwargs)
        else:
            self.full_clean()
            super().save(*args, **kwargs)

        self.sync_from_bin_collection_events()
        self.sync_from_household_collections()

        if self.actual_end_time:
            from datetime import datetime
            from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
            assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
            if assignment and assignment.status != DailyTripAssignment.STATUS_COMPLETED:
                ended_at = timezone.make_aware(
                    datetime.combine(self.trip_date, self.actual_end_time)
                )
                assignment.mark_ended(at=ended_at)

    @property
    def trip_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        if self.trip_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        return None

    @property
    def staff_template(self):
        from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
        if self.staff_template_id:
            return StaffTemplate.objects.filter(unique_id=self.staff_template_id).first()
        return None

    @property
    def alt_staff_template(self):
        from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
        if self.alt_staff_template_id:
            return AlternativeStaffTemplate.objects.filter(unique_id=self.alt_staff_template_id).first()
        return None

    @property
    def company(self):
        from app.models.superadmin_masters.company import Company
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None

    @property
    def project(self):
        from app.models.superadmin_masters.project import Project
        if self.project_id:
            return Project.objects.filter(unique_id=self.project_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def collection_point(self):
        from app.models.core_modules.schedule_setup.collection_point import Collection_point
        if self.collection_point_id:
            return Collection_point.objects.filter(unique_id=self.collection_point_id).first()
        return None

    @property
    def waste_type(self):
        from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
        if self.waste_type_id:
            return WasteType.objects.filter(unique_id=self.waste_type_id).first()
        return None

    @property
    def driver(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        if self.driver_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.driver_id).first()
        return None

    @property
    def operator(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        if self.operator_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.operator_id).first()
        return None

    @property
    def vehicle(self):
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        if self.vehicle_id:
            return VehicleCreation.objects.filter(unique_id=self.vehicle_id).first()
        return None

    @property
    def verified_by_user(self):
        if self.verified_by:
            return Account.objects.filter(account_id=self.verified_by).first()
        return None