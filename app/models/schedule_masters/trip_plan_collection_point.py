from django.core.exceptions import ValidationError
from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo


def generate_tpcp_id():
    return f"TPCP-{generate_unique_id()}"


class TripPlanCollectionPoint(BaseMaster):
    """Master stop list for a TripPlan."""

    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"

    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Bin Collection"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_tpcp_id,
        editable=False,
    )

    trip_plan_id = models.CharField(max_length=30, null=True, blank=True)

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
        db_index=True,
    )

    # --- Bin Collection fields (required when collection_type == bin_collection) ---
    collection_point_id = models.CharField(max_length=30, null=True, blank=True)
    bin_id = models.CharField(max_length=30, null=True, blank=True)

    # --- Household/Bulk Collection fields (required when collection_type == household_collection or bulk_waste_collection) ---
    customer_id = models.CharField(max_length=30, null=True, blank=True)

    zone_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    sequence = models.PositiveIntegerField(
        help_text="Visit order within the route.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive stops are skipped during auto-assignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("trip_plan_collection_point_list", "trip_plan_collection_point_detail")

    class Meta:
        ordering = ["trip_plan_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_plan_id", "is_active"]),
            models.Index(fields=["trip_plan_id", "collection_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_plan_id", "sequence"],
                name="uniq_sequence_per_trip_plan",
            ),
        ]

    def clean(self):
        # A stop's type must match its plan's declared collection_type - a
        # plan generates exactly one category of daily work (see
        # TripPlan.collection_type), so a household_collection plan can only
        # carry household-type stops, and a bin_collection plan only bin
        # stops. (Whether a bulk stop may be added manually is enforced at
        # the API/serializer layer; the auto-generated bulk placeholder row
        # is still valid here.)
        if self.trip_plan_id:
            from app.models.schedule_masters.trip_plan import TripPlan
            tp = TripPlan.objects.filter(unique_id=self.trip_plan_id).first()
            if tp and self.collection_type != tp.collection_type:
                raise ValidationError(
                    {"collection_type": "Stop type must match the trip plan's collection type."}
                )
        if self.collection_type == self.COLLECTION_TYPE_BIN:
            if not self.collection_point_id:
                raise ValidationError({"collection_point_id": "Collection point is required for bin collection."})
            if not self.bin_id:
                raise ValidationError({"bin_id": "Bin is required for bin collection."})
        elif self.collection_type in {self.COLLECTION_TYPE_HOUSEHOLD, self.COLLECTION_TYPE_BULK}:
            if not self.customer_id and not self.ward_id and not self.panchayat_id and not self.trip_plan_id:
                raise ValidationError(
                    {"customer_id": "Select a customer or assign collection to a geographic area."}
                )

    def save(self, *args, **kwargs):
        if self.collection_point_id:
            from app.models.schedule_masters.collection_point import Collection_point
            cp = Collection_point.objects.filter(unique_id=self.collection_point_id).first()
            if cp:
                copy_flat_geo(self, cp)
        elif self.customer_id:
            from app.models.customers.customercreation import CustomerCreation
            cust = CustomerCreation.objects.filter(unique_id=self.customer_id).first()
            if cust:
                copy_flat_geo(self, cust)
        elif self.trip_plan_id:
            from app.models.schedule_masters.trip_plan import TripPlan
            tp = TripPlan.objects.filter(unique_id=self.trip_plan_id).first()
            if tp:
                copy_flat_geo(self, tp)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.collection_type in {self.COLLECTION_TYPE_HOUSEHOLD, self.COLLECTION_TYPE_BULK} and self.customer_id:
            return f"{self.trip_plan_id} -> customer:{self.customer_id} (seq {self.sequence})"
        return (
            f"{self.trip_plan_id} -> "
            f"{self.collection_point_id} (seq {self.sequence})"
        )

    @property
    def trip_plan(self):
        from app.models.schedule_masters.trip_plan import TripPlan
        if self.trip_plan_id:
            return TripPlan.objects.filter(unique_id=self.trip_plan_id).first()
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
    def collection_point(self):
        from app.models.schedule_masters.collection_point import Collection_point
        if self.collection_point_id:
            return Collection_point.objects.filter(unique_id=self.collection_point_id).first()
        return None

    @property
    def bin(self):
        from app.models.assets.bins import Bins
        if self.bin_id:
            return Bins.objects.filter(unique_id=self.bin_id).first()
        return None

    @property
    def customer(self):
        from app.models.customers.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
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