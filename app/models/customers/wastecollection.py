from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo


def generate_wastecollection_id():
    """Generate readable prefixed ID, e.g., WASTE-20251028001"""
    return f"WASTE-{generate_unique_id()}"


class WasteCollection(BaseMaster):
    # Same vocabulary as DailyTripHouseholdCollection.STATUS_CHOICES
    # (app/models/schedule_masters/daily_trip_household_collection.py), the
    # canonical household-stop status used across the app.
    STATUS_PENDING = "Pending"
    STATUS_COLLECTED = "Collected"
    STATUS_NOT_AVAILABLE = "Not Available"
    STATUS_COLLECT_LATER = "Collect Later"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_NOT_AVAILABLE, "Not Available"),
        (STATUS_COLLECT_LATER, "Collect Later"),
    ]

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_wastecollection_id,
        editable=False,
    )

    #  Link one customer – all details fetched via relation
    customer_id = models.CharField(max_length=30, null=True, blank=True)

    # Optional link to the trip assignment that triggered this collection
    trip_assignment_id = models.CharField(max_length=50, null=True, blank=True)

    # Geography — auto-inherited from the linked household on save when left
    # blank (via copy_flat_geo), but selectable/editable so a collection can
    # be scoped independently. Mirrors TN_Iwms's WasteCollection geo block,
    # adapted to IWMS's flat zone/ward/panchayat fields.
    ward_id = models.CharField(max_length=30, null=True, blank=True)

    #  Waste details
    wet_waste = models.FloatField(default=0.0)
    dry_waste = models.FloatField(default=0.0)
    mixed_waste = models.FloatField(default=0.0)
    sanitary_waste = models.FloatField(default=0.0)
    total_quantity = models.FloatField(default=0.0)

    # Best-effort proof photo carried over from the legacy WasteCollectionSub
    # row(s) this collection was bridged from (see
    # WasteCollectionBluetoothViewSet._sync_to_household_collection) — a
    # relative MEDIA path, same convention as WasteCollectionSub.image. Null
    # when the collection wasn't made through that bridge, or none of its
    # sub-rows carried a photo.
    image = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    # Collection date is now a plain, user-editable field (matching
    # BinCollectionEvent.collection_date) rather than auto-set on creation.
    collection_date = models.DateField(default=None, null=True, blank=True)
    collection_time = models.TimeField(auto_now_add=True)

    CASCADE_SOFT_DELETE = ("daily_trip_household_collections",)
    CACHE_SCOPES = ("waste_collection_list", "waste_collection_detail")

    class Meta:
        verbose_name = "Waste Collection"
        verbose_name_plural = "Waste Collections"
        ordering = ["-collection_date", "-collection_time"]

    def __str__(self):
        """Readable entry with linked customer and location."""
        customer_name = "Unknown"
        if self.customer_id:
            from app.models.customers.customercreation import CustomerCreation
            cust = CustomerCreation.objects.filter(unique_id=self.customer_id).first()
            if cust:
                customer_name = cust.customer_name
        ward = ""
        if self.ward_id:
            from app.models.masters.ward import Ward
            w = Ward.objects.filter(unique_id=self.ward_id).first()
            if w:
                ward = w.ward_name
        zone = ""
        if self.customer_id:
            from app.models.customers.customercreation import CustomerCreation
            cust = CustomerCreation.objects.filter(unique_id=self.customer_id).first()
            if cust and cust.zone_id:
                from app.models.masters.zone import Zone
                z = Zone.objects.filter(unique_id=cust.zone_id).first()
                if z:
                    zone = z.zone_name
        city = ""
        if self.customer_id:
            from app.models.customers.customercreation import CustomerCreation
            cust = CustomerCreation.objects.filter(unique_id=self.customer_id).first()
            if cust and cust.city_id:
                from app.models.masters.city import City
                c = City.objects.filter(unique_id=cust.city_id).first()
                if c:
                    city = c.name
        panchayat = ""
        if self.customer_id:
            from app.models.customers.customercreation import CustomerCreation
            cust = CustomerCreation.objects.filter(unique_id=self.customer_id).first()
            if cust and cust.panchayat_id:
                from app.models.masters.panchayat import Panchayat
                p = Panchayat.objects.filter(unique_id=cust.panchayat_id).first()
                if p:
                    panchayat = p.panchayat_name
        return f"{customer_name} - {ward or zone or city} - {panchayat}"

    def save(self, *args, **kwargs):
        """Auto-calculate total and inherit geography from the household."""
        from django.utils import timezone

        self.total_quantity = (
            (self.wet_waste or 0)
            + (self.dry_waste or 0)
            + (self.mixed_waste or 0)
            + (self.sanitary_waste or 0)
        )
        # collection_date is user-editable but still needs a sane default
        # when omitted (e.g. seeders/legacy callers that relied on the old
        # auto_now_add behaviour).
        if not self.collection_date:
            self.collection_date = timezone.localdate()
        # If no geography was supplied, copy the household's ward (and any
        # other flat geo FK WasteCollection may gain later) so the record is
        # always scoped even when created via seeders/admin/API.
        if self.customer_id and not self.ward_id:
            from app.models.customers.customercreation import CustomerCreation
            cust = CustomerCreation.objects.filter(unique_id=self.customer_id).first()
            if cust:
                copy_flat_geo(self, cust)
        super().save(*args, **kwargs)

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
    def customer(self):
        from app.models.customers.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
        return None

    @property
    def trip_assignment(self):
        from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
        if self.trip_assignment_id:
            return DailyTripAssignment.objects.filter(unique_id=self.trip_assignment_id).first()
        return None

    @property
    def ward(self):
        from app.models.masters.ward import Ward
        if self.ward_id:
            return Ward.objects.filter(unique_id=self.ward_id).first()
        return None