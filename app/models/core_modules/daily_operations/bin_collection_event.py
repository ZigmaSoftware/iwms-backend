from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo


def generate_bin_collection_event_id():
    return f"BCE-{generate_unique_id(length=10)}"


class BinCollectionEvent(BaseMaster):
    """One row per operator scan-and-submit. Permanent audit ledger."""

    STATUS_COLLECTED = "Collected"
    STATUS_NOT_COLLECTED = "Not Collected"
    STATUS_COLLECT_LATER = "Collect Later"

    STATUS_CHOICES = [
        (STATUS_COLLECTED, "Collected"),
        (STATUS_NOT_COLLECTED, "Not Collected"),
        (STATUS_COLLECT_LATER, "Collect Later"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_bin_collection_event_id,
        editable=False,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    trip_assignment_id = models.CharField(max_length=50, null=True, blank=True)
    trip_collection_point_id = models.CharField(max_length=30, null=True, blank=True)

    collection_point_id = models.CharField(max_length=30, null=True, blank=True)
    bin_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    waste_type_id = models.CharField(max_length=30, null=True, blank=True)
    vehicle_id = models.CharField(max_length=30, null=True, blank=True)
    vehicle_breakdown_id = models.CharField(max_length=30, null=True, blank=True)

    collected_weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_COLLECTED,
        db_index=True,
    )
    status_reason = models.TextField(null=True, blank=True)
    collection_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
        help_text="Date on which this bin collection was performed.",
    )

    driver_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    driver_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("bin_collection_event_list", "bin_collection_event_detail")

    class Meta:
        ordering = ["-collection_date", "-created_at"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "created_at"]),
            models.Index(fields=["collection_date"]),
        ]

    def save(self, *args, **kwargs):
        # Inherit corporation/local-body scope from the parent trip
        # assignment on first write. Only fills in blanks — explicit
        # selections from the form are preserved. Mirrors TN_Iwms's
        # BinCollectionEvent.save (secondary_bin_collection_event.py),
        # adapted to IWMS's flat zone/ward/panchayat geo fields (the
        # assignment has no single `ward` FK, only a `wards` M2M, so ward/
        # zone are resolved separately when the assignment carries exactly
        # one ward).
        if self.trip_assignment_id and not self.panchayat_id:
            from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
            assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
            if assignment:
                copy_flat_geo(self, assignment)
        if self.trip_assignment_id and not self.ward_id:
            from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
            from app.models.masters.ward import Ward
            assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
            if assignment:
                ward_ids = assignment.get_ward_ids()
                if len(ward_ids) == 1:
                    ward = Ward.objects.filter(unique_id=ward_ids[0]).first()
                    if ward:
                        self.ward_id = ward.unique_id
                        if not self.zone_id:
                            self.zone_id = ward.zone_id
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id

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
    def trip_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
        if self.trip_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        return None

    @property
    def trip_collection_point(self):
        from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
        if self.trip_collection_point_id:
            return DailyTripCollectionPoint.objects.filter(unique_id=self.trip_collection_point_id).first()
        return None

    @property
    def collection_point(self):
        from app.models.core_modules.schedule_setup.collection_point import Collection_point
        if self.collection_point_id:
            return Collection_point.objects.filter(unique_id=self.collection_point_id).first()
        return None

    @property
    def bin(self):
        from app.models.masters.waste_masters.bins import Bins
        if self.bin_id:
            return Bins.objects.filter(unique_id=self.bin_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def ward(self):
        from app.models.masters.ward import Ward
        if self.ward_id:
            return Ward.objects.filter(unique_id=self.ward_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def waste_type(self):
        from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
        if self.waste_type_id:
            return WasteType.objects.filter(unique_id=self.waste_type_id).first()
        return None

    @property
    def vehicle(self):
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        if self.vehicle_id:
            return VehicleCreation.objects.filter(unique_id=self.vehicle_id).first()
        return None

    @property
    def vehicle_breakdown(self):
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
        if self.vehicle_breakdown_id:
            return VehicleBreakdown.objects.filter(unique_id=self.vehicle_breakdown_id).first()
        return None