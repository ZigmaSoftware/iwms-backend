from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def geneate_collection_point_id():
    return f"CP-{generate_unique_id()}"


class Collection_point(BaseMaster):
    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"

    # Full legacy set — household is kept here so pre-existing household
    # collection-point rows remain loadable and never fail on read.
    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Bin Collection"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    # Choices exposed for collection points at the API boundary. Household
    # collection belongs to household stops (DailyTripHouseholdCollection),
    # not collection points, so it is intentionally excluded from new writes.
    COLLECTION_TYPE_CP_CHOICES = [
        (COLLECTION_TYPE_BIN, "Bin Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=geneate_collection_point_id,
        editable=False
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    state_id = models.CharField(max_length=30, null=True, blank=True)
    city_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)

    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)

    # Store ward IDs as comma-separated string
    ward_ids = models.TextField(blank=True, default="")

    CASCADE_SOFT_DELETE = (
        "bin",
        "trip_plan_cps",
        "daily_trip_logs",
        "daily_trip_cps",
        "bin_collection_events",
    )
    CACHE_SCOPES = ("collection_point_list", "collection_point_detail")

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
    )

    cp_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.panchayat_id and not self.get_ward_ids():
            raise ValidationError("A collection point must have either a panchayat or at least one ward.")

    def __str__(self):
        if self.panchayat_id:
            from app.models.masters.panchayat import Panchayat
            panchayat_name = Panchayat.objects.filter(unique_id=self.panchayat_id).values_list("panchayat_name", flat=True).first()
            return f"{self.cp_name} (Panchayat: {panchayat_name})"
        return self.cp_name

    def get_ward_ids(self):
        return [w for w in self.ward_ids.split(",") if w]

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
    def state(self):
        from app.models.superadmin.common_masters.state import State
        if self.state_id:
            return State.objects.filter(unique_id=self.state_id).first()
        return None

    @property
    def city(self):
        from app.models.masters.city import City
        if self.city_id:
            return City.objects.filter(unique_id=self.city_id).first()
        return None

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
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
    def wards(self):
        from app.models.masters.ward import Ward
        ward_ids = self.get_ward_ids()
        return Ward.objects.filter(unique_id__in=ward_ids)