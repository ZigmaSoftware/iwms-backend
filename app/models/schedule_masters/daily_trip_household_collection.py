from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_dthc_id():
    return f"DTHC-{generate_unique_id(length=10)}"


class DailyTripHouseholdCollection(BaseMaster):
    """One row per household stop within a daily trip assignment.

    Created automatically (via signal) when a DailyTripAssignment is saved,
    mirroring every household_collection stop from the linked TripPlan.
    Marked collected when the corresponding WasteCollection record is saved.
    """

    STATUS_PENDING = "Pending"
    STATUS_COLLECTED = "Collected"
    STATUS_COLLECT_LATER = "Collect Later"
    # "Not Available" is the canonical label for a household that couldn't be
    # collected (mobile app's "Not available" action). Kept as STATUS_MISSED
    # for backward-compat with existing call sites; value/label match TN_Iwms.
    STATUS_MISSED = "Not Available"
    # Legacy values kept so historical rows still validate.
    STATUS_NOT_COLLECTED = "Not Collected"
    STATUS_SKIPPED = "Skipped"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_COLLECT_LATER, "Collect Later"),
        (STATUS_MISSED, "Not Available"),
        (STATUS_NOT_COLLECTED, "Not Collected"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"

    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_dthc_id,
        editable=False,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    trip_assignment_id = models.CharField(max_length=50, null=True, blank=True)

    customer_id = models.CharField(max_length=30, null=True, blank=True)

    # Filled when the WasteCollection record is saved for this customer + trip
    waste_collection_id = models.CharField(max_length=30, null=True, blank=True)

    zone_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_HOUSEHOLD,
        db_index=True,
    )

    sequence = models.PositiveIntegerField(default=1)

    is_collected = models.BooleanField(default=False, db_index=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Copied from WasteCollection.total_quantity when marked collected.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    # Captured when a driver/operator marks the stop Not Available/Collect
    # Later from the app (no WasteCollection exists in that case, so the
    # reason and device location are recorded here for audit).
    status_reason = models.TextField(null=True, blank=True)
    status_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    status_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )

    # Set by the Re-Trip flow (app/services/retrip_service.py) when this stop
    # was still pending and got moved to a continuation trip.
    carried_to_assignment = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("daily_trip_household_collection_list", "daily_trip_household_collection_detail")

    class Meta:
        ordering = ["trip_assignment_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "is_collected"]),
            models.Index(fields=["trip_assignment_id", "sequence"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_assignment_id", "customer_id", "collection_type"],
                name="uniq_household_per_trip_assignment",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.trip_assignment_id and not self.company_id:
            from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
            assignment = DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
            if assignment:
                self.company_id = assignment.company_id
                self.project_id = assignment.project_id
        # Denormalise location from customer
        if self.customer_id and not self.panchayat_id:
            from app.models.customers.customercreation import CustomerCreation
            customer = CustomerCreation.objects.filter(unique_id=self.customer_id).first()
            if customer:
                self.panchayat_id = customer.panchayat_id
                self.ward_id = customer.ward_id
                self.zone_id = customer.zone_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_assignment_id}:customer:{self.customer_id}"

    def mark_collected(self, waste_collection, collected_at=None):
        from decimal import Decimal
        self.waste_collection_id = waste_collection.unique_id if hasattr(waste_collection, 'unique_id') else waste_collection
        self.collected_weight_kg = Decimal(str(waste_collection.total_quantity or 0))
        self.collected_at = collected_at or timezone.now()
        self.is_collected = True
        self.status = self.STATUS_COLLECTED
        self.status_reason = None
        self.save(update_fields=[
            "waste_collection_id",
            "collected_weight_kg",
            "collected_at",
            "is_collected",
            "status",
            "status_reason",
            "updated_at",
        ])

    def mark_status(self, status, reason=None, latitude=None, longitude=None):
        """Mark this household/bulk stop Not Available / Collect Later from
        the operator app. No WasteCollection is created in that case."""
        self.status = status
        self.status_reason = reason
        self.status_latitude = latitude
        self.status_longitude = longitude
        self.is_collected = False
        self.collected_at = None
        if status == self.STATUS_MISSED:
            self.collected_weight_kg = None
        self.save(update_fields=[
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "is_collected",
            "collected_at",
            "collected_weight_kg",
            "updated_at",
        ])

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
    def customer(self):
        from app.models.customers.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
        return None

    @property
    def waste_collection(self):
        from app.models.customers.wastecollection import WasteCollection
        if self.waste_collection_id:
            return WasteCollection.objects.filter(unique_id=self.waste_collection_id).first()
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
    def carried_to_assignment_obj(self):
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        if self.carried_to_assignment:
            return DailyTripAssignment.objects.filter(unique_id=self.carried_to_assignment).first()
        return None