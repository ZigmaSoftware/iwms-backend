from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_daily_trip_cp_id():
    return f"DTCP-{generate_unique_id(length=10)}"


class DailyTripCollectionPoint(BaseMaster):
    CASCADE_SOFT_DELETE = ("bin_collection_event",)
    CACHE_SCOPES = ("daily_trip_collection_point_list", "daily_trip_collection_point_detail")

    STATUS_PENDING = "Pending"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COLLECTED = "Collected"
    STATUS_SKIPPED = "Skipped"
    STATUS_MISSED = "Missed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_MISSED, "Missed"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_daily_trip_cp_id,
        editable=False,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    trip_assignment_id = models.CharField(max_length=50, null=True, blank=True)

    collection_point_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    bin_id = models.CharField(max_length=30, null=True, blank=True)

    sequence = models.PositiveIntegerField(default=1)
    
    is_collected = models.BooleanField(default=False, db_index=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.CharField(max_length=30, null=True, blank=True)
    collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    status_reason = models.TextField(null=True, blank=True)
    status_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    status_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )

    # Set by the Re-Trip flow (app/services/retrip_service.py) when this stop
    # was still pending and got moved to a continuation trip, so the Daily
    # Trip Plan / Trip Log screens can show "Assigned to Next Trip" instead
    # of a bare Pending with no explanation.
    carried_to_assignment = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_assignment_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "is_collected"]),
            models.Index(fields=["trip_assignment_id", "sequence"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_assignment_id", "collection_point_id", "bin_id"],
                name="uniq_trip_cp_bin_per_assignment",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.trip_assignment_id and not self.company_id:
            from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
            assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
            if assignment:
                self.company_id = assignment.company_id
                self.project_id = assignment.project_id
        if self.collection_point_id:
            from app.models.schedule_masters.collection_point import Collection_point
            collection_point = Collection_point.objects.filter(unique_id=self.collection_point_id).first()
            if collection_point:
                self.panchayat_id = collection_point.panchayat_id
                from app.models.masters.ward import Ward
                ward_ids = collection_point.get_ward_ids()
                if ward_ids:
                    first_ward = Ward.objects.filter(unique_id=ward_ids[0]).first()
                    if first_ward:
                        self.ward_id = first_ward.unique_id
                        self.zone_id = first_ward.zone_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_assignment_id}:{self.collection_point_id}"

    def mark_collected(self, weight_kg, collected_by, collected_at=None):
        self.collected_weight_kg = weight_kg
        self.collected_by = collected_by
        self.collected_at = collected_at or timezone.now()
        self.is_collected = True
        self.status = self.STATUS_COLLECTED
        self.status_reason = None
        self.status_latitude = None
        self.status_longitude = None
        self.save(update_fields=[
            "collected_weight_kg",
            "collected_by",
            "collected_at",
            "is_collected",
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "updated_at",
        ])
        # Driver app write path — ending the trip is now a driver-confirmed
        # action (see TripCompletionNudge), not an automatic side effect of
        # the last scan. Admin/web edits to this model still auto-close (see
        # mark_completed_if_all_cps_collected's docstring).
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        if assignment:
            assignment.mark_completed_if_all_cps_collected(auto_end=False)

    def mark_status(self, status, reason, latitude=None, longitude=None):
        """Mark this stop Missed/Skipped (collect-later) from the operator app.

        No weight is recorded — Missed/Skipped stops are operationally
        resolved for the day but contribute zero weight. Mirrors TN_Iwms's
        DailyTripCollectionPoint.mark_status.
        """
        self.status = status
        self.status_reason = reason
        self.status_latitude = latitude
        self.status_longitude = longitude
        self.is_collected = False
        self.collected_at = None
        self.collected_by = None
        if status in {self.STATUS_SKIPPED, self.STATUS_MISSED}:
            self.collected_weight_kg = None
        self.save(update_fields=[
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "is_collected",
            "collected_at",
            "collected_by",
            "collected_weight_kg",
            "updated_at",
        ])
        # See mark_collected's comment just above — driver app write path.
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        if assignment:
            assignment.mark_completed_if_all_cps_collected(auto_end=False)

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
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        if self.trip_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        return None

    @property
    def collection_point(self):
        from app.models.schedule_masters.collection_point import Collection_point
        if self.collection_point_id:
            return Collection_point.objects.filter(unique_id=self.collection_point_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def ward(self):
        from app.models.masters.ward import Ward
        if self.ward_id:
            return Ward.objects.filter(unique_id=self.ward_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def bin(self):
        from app.models.assets.bins import Bins
        if self.bin_id:
            return Bins.objects.filter(unique_id=self.bin_id).first()
        return None

    @property
    def collected_by_user(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.collected_by:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.collected_by).first()
        return None

    @property
    def carried_to_assignment_obj(self):
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        if self.carried_to_assignment:
            return DailyTripAssignment.objects.filter(unique_id=self.carried_to_assignment).first()
        return None