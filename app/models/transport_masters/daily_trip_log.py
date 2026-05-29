from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app.models.assets.bin import Bin
from app.models.assets.collection_point import Collection_point
from app.models.masters.panchayat import Panchayat
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.base_models import Account, BaseMaster


def _generate_daily_trip_log_unique_id(company_id, project_id):
    today = timezone.localdate()
    prefix = f"DTL-{today.year}-{today.month:02d}"
    count = DailyTripLog.objects.filter(
        company_id=company_id,
        project_id=project_id,
        unique_id__startswith=f"{prefix}-",
    ).count()
    return f"{prefix}-{count + 1:03d}"


class DailyTripLog(BaseMaster):
    LOG_STATUS_DRAFT = "Draft"
    LOG_STATUS_SUBMITTED = "Submitted"
    LOG_STATUS_VERIFIED = "Verified"

    LOG_STATUS_CHOICES = [
        (LOG_STATUS_DRAFT, "Draft"),
        (LOG_STATUS_SUBMITTED, "Submitted"),
        (LOG_STATUS_VERIFIED, "Verified"),
    ]

    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    trip_assignment_id = models.OneToOneField(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="daily_trip_log",
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="daily_trip_logs",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        related_name="daily_trip_logs",
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )

    trip_date = models.DateField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="driver_id",
        to_field="staff_unique_id",
        related_name="daily_trip_logs_as_driver",
    )
    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="operator_id",
        to_field="staff_unique_id",
        related_name="daily_trip_logs_as_operator",
    )
    extra_operator_ids = models.ManyToManyField(
        Staffcreation,
        blank=True,
        related_name="daily_trip_logs_as_extra_operator",
    )

    collected_weight_kg = models.DecimalField(max_digits=10, decimal_places=2)

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )
    bin_ids = models.ManyToManyField(
        Bin,
        blank=True,
        related_name="daily_trip_logs",
    )

    remarks = models.TextField(null=True, blank=True)
    log_status = models.CharField(
        max_length=20,
        choices=LOG_STATUS_CHOICES,
        default=LOG_STATUS_DRAFT,
        db_index=True,
    )

    verified_by = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="verified_by",
        related_name="verified_daily_trip_logs",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-trip_date", "-created_at"]
        indexes = [
            models.Index(fields=["trip_date", "log_status"]),
            models.Index(fields=["company_id", "project_id", "trip_date"]),
            models.Index(fields=["collection_point_id", "trip_date"]),
        ]

    def __str__(self):
        return self.unique_id

    def _resolve_effective_staff_template(self):
        assignment = self.trip_assignment_id
        return assignment.alt_staff_template_id or assignment.staff_template_id

    def autofill_from_assignment(self):
        assignment = self.trip_assignment_id
        if not assignment:
            return

        self.company_id = assignment.company_id
        self.project_id = assignment.project_id
        self.panchayat_id = assignment.panchayat_id
        self.collection_point_id = assignment.collection_point_id
        self.waste_type_id = assignment.waste_type_id
        self.trip_date = assignment.trip_date
        self.actual_start_time = self.actual_start_time or assignment.actual_start_time
        self.actual_end_time = self.actual_end_time or assignment.actual_end_time

        staff_template = self._resolve_effective_staff_template()
        if staff_template:
            self.driver_id = staff_template.driver_id
            self.operator_id = staff_template.operator_id

        trip_definition = assignment.trip_definition_id
        routeplan = getattr(trip_definition, "routeplan_id", None)
        if routeplan and routeplan.vehicle_id:
            self.vehicle_id = routeplan.vehicle_id

    def clean(self):
        super().clean()

        if not self.trip_assignment_id:
            return

        assignment = self.trip_assignment_id
        if assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise ValidationError("Cannot create a log for a cancelled trip.")

        if self.pk:
            previous = DailyTripLog.objects.filter(pk=self.pk).first()
            if previous and previous.log_status == self.LOG_STATUS_VERIFIED:
                raise ValidationError("Verified trip logs are read-only.")

        if self.collected_weight_kg is not None and self.collected_weight_kg <= 0:
            raise ValidationError("collected_weight_kg must be greater than 0.")

        vehicle_capacity = getattr(self.vehicle_id, "capacity", None)
        trip_capacity = getattr(assignment.trip_definition_id, "max_vehicle_capacity_kg", None)
        capacity = vehicle_capacity or trip_capacity
        if capacity and self.collected_weight_kg is not None:
            if Decimal(self.collected_weight_kg) > Decimal(capacity):
                raise ValidationError("collected_weight_kg cannot exceed vehicle capacity.")

    def save(self, *args, **kwargs):
        self.autofill_from_assignment()
        if not self.unique_id:
            self.unique_id = _generate_daily_trip_log_unique_id(
                self.company_id, self.project_id
            )

        self.full_clean()
        super().save(*args, **kwargs)

        if self.log_status in {self.LOG_STATUS_SUBMITTED, self.LOG_STATUS_VERIFIED}:
            assignment = self.trip_assignment_id
            if assignment.status != DailyTripAssignment.STATUS_COMPLETED:
                now_time = timezone.localtime().time()
                update_fields = ["status", "updated_at"]
                assignment.status = DailyTripAssignment.STATUS_COMPLETED
                if not assignment.actual_end_time:
                    assignment.actual_end_time = self.actual_end_time or now_time
                    update_fields.append("actual_end_time")
                assignment.save(update_fields=update_fields)
