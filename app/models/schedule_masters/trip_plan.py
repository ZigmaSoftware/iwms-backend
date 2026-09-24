# ============================================================
# 3. trip_plan.py  (merged RoutePlan + TripDefinition)
# ============================================================
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_trip_plan_id():
    return f"TPLAN-{generate_unique_id()}"


class TripPlan(BaseMaster):
    """Single source of truth for route + trip configuration."""

    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"

    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Bin Collection"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    class ApprovalStatus(models.TextChoices):
        PENDING  = "PENDING",  "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Status(models.TextChoices):
        ACTIVE   = "ACTIVE",   "Active"
        INACTIVE = "INACTIVE", "Inactive"

    # ---- identifier ------------------------------------------------
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_trip_plan_id,
        editable=False,
    )
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="e.g. RAVI-TN01AB1234-01",
    )

    # ---- tenancy ---------------------------------------------------
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    # ---- WHERE -----------------------------------------------------
    district_id = models.CharField(max_length=30, null=True, blank=True)
    city_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    block_panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    
    # Store ward IDs as comma-separated string
    ward_ids = models.TextField(blank=True, default="")

    # ---- WHO -------------------------------------------------------
    staff_template_id = models.CharField(max_length=30, null=True, blank=True)
    vehicle_id = models.CharField(max_length=30, null=True, blank=True)
    supervisor_id = models.CharField(max_length=30, null=True, blank=True)

    # ---- WHAT ------------------------------------------------------
    property_id = models.CharField(max_length=30, null=True, blank=True)
    sub_property_id = models.CharField(max_length=30, null=True, blank=True)
    waste_type_id = models.CharField(max_length=30, null=True, blank=True)
    waste_type_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of waste type unique_ids allowed for this trip plan (legacy).",
    )
    # Store waste type IDs as comma-separated string
    waste_type_ids_csv = models.TextField(blank=True, default="")
    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
        db_index=True,
        help_text="One Trip Plan can generate only one category of daily work.",
    )
    trip_trigger_weight_kg = models.PositiveIntegerField(
        help_text="Collected weight (kg) that triggers a trip dispatch.",
    )
    max_vehicle_capacity_kg = models.PositiveIntegerField(
        help_text="Hard ceiling for vehicle load (kg).",
    )

    # ---- WHEN -------------------------------------------------------
    scheduled_time = models.TimeField(
        help_text="Default departure time for trips generated from this plan.",
    )
    # ---- AUTO-ASSIGN ------------------------------------------------
    is_auto_assign = models.BooleanField(
        default=False,
        help_text="If true, DailyTripAssignment will be auto-generated from this plan.",
        db_index=True,
    )
    # repeat_days: list of integers 0-6 where Monday=0. If null or empty, no repeats.
    repeat_days = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON list of weekdays (0=Monday..6=Sunday) when auto-assign runs.",
    )

    # ---- workflow --------------------------------------------------
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("plan_collection_points", "daily_trip_assignments")
    CACHE_SCOPES = ("trip_plan_list", "trip_plan_detail")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["collection_type"]),
            models.Index(fields=["status", "approval_status"]),
            models.Index(fields=["display_code"]),
        ]
        constraints = []

    def _generate_display_code(self):
        driver_name = "DRV"
        if self.staff_template_id:
            from app.models.schedule_masters.staff_template import StaffTemplate
            tmpl = StaffTemplate.objects.filter(unique_id=self.staff_template_id).first()
            if tmpl and tmpl.driver_id:
                from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
                driver = StaffcreationOfficeDetails.objects.filter(
                    staff_unique_id=tmpl.driver_id
                ).first()
                if driver and driver.employee_name:
                    driver_name = driver.employee_name[:6].upper().replace(" ", "")
        vehicle_no = "VEH"
        if self.vehicle_id:
            from app.models.transport_masters.vehicleCreation import VehicleCreation
            veh = VehicleCreation.objects.filter(unique_id=self.vehicle_id).first()
            if veh:
                vehicle_no = veh.vehicle_no.upper().replace(" ", "")

        base = f"{driver_name}-{vehicle_no}"
        last = (
            TripPlan.objects
            .filter(display_code__startswith=base)
            .aggregate(max_code=Max("display_code"))
            .get("max_code")
        )
        seq = 0
        if last:
            try:
                seq = int(last.split("-")[-1])
            except ValueError:
                pass
        return f"{base}-{seq + 1:02d}"

    def save(self, *args, **kwargs):
        if not self.display_code:
            self.display_code = self._generate_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_code or self.unique_id

    def get_ward_ids(self):
        return [w for w in self.ward_ids.split(",") if w]

    def get_waste_type_ids(self):
        return [w for w in self.waste_type_ids_csv.split(",") if w]

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
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

    @property
    def city(self):
        from app.models.masters.city import City
        if self.city_id:
            return City.objects.filter(unique_id=self.city_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def block_panchayat_union(self):
        from app.models.masters.block_panchayat_union import BlockPanchayatUnion
        if self.block_panchayat_union_id:
            return BlockPanchayatUnion.objects.filter(unique_id=self.block_panchayat_union_id).first()
        return None

    @property
    def wards(self):
        from app.models.masters.ward import Ward
        return Ward.objects.filter(unique_id__in=self.get_ward_ids())

    @property
    def staff_template(self):
        from app.models.schedule_masters.staff_template import StaffTemplate
        if self.staff_template_id:
            return StaffTemplate.objects.filter(unique_id=self.staff_template_id).first()
        return None

    @property
    def vehicle(self):
        from app.models.transport_masters.vehicleCreation import VehicleCreation
        if self.vehicle_id:
            return VehicleCreation.objects.filter(unique_id=self.vehicle_id).first()
        return None

    @property
    def supervisor(self):
        from app.models.staff_creations.staffcreation import StaffcreationOfficeDetails
        if self.supervisor_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.supervisor_id).first()
        return None

    @property
    def property_obj(self):
        from app.models.waste_types.property import Property
        if self.property_id:
            return Property.objects.filter(unique_id=self.property_id).first()
        return None

    @property
    def sub_property_obj(self):
        from app.models.waste_types.subproperty import SubProperty
        if self.sub_property_id:
            return SubProperty.objects.filter(unique_id=self.sub_property_id).first()
        return None

    @property
    def waste_type(self):
        from app.models.staff_creations.waste_collection_bluetooth import WasteType
        if self.waste_type_id:
            return WasteType.objects.filter(unique_id=self.waste_type_id).first()
        return None
