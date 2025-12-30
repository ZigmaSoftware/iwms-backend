from django.db import models
from django.db.models import Q

from .utils.comfun import generate_unique_id
from .ward import Ward
from .zone import Zone
from .property import Property
from .subproperty import SubProperty
from .customercreation import CustomerCreation
from .userCreation import User


def generate_route_stop_id():
    """Readable prefixed ID for route stops."""
    return f"RSTP-{generate_unique_id()}"


class RouteStop(models.Model):
    class StopType(models.TextChoices):
        HOUSE = "house", "House"
        APARTMENT = "apartment", "Apartment"
        COMMERCIAL = "commercial", "Commercial"
        INDUSTRIAL = "industrial", "Industrial"
        INSTITUTIONAL = "institutional", "Institutional"
        DEPOT = "depot", "Depot"
        TRANSFER = "transfer", "Transfer Station"
        LANDFILL = "landfill", "Landfill"
        BREAK = "break", "Break"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"
        DEFERRED = "deferred", "Deferred"

    unique_id = models.CharField(
        max_length=50,
        unique=True,
        default=generate_route_stop_id,
        editable=False,
        help_text="Stable external ID for integrations and mobile clients",
    )

    route_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Logical route identifier; replace with FK when route model is introduced",
    )

    ward = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="route_stops",
    )
    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="route_stops",
        null=True,
        blank=True,
    )
    cluster_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Grouping key for stacked markers (e.g., apartments)",
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="route_stops",
    )
    sub_property = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        related_name="route_stops",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        related_name="route_stops",
        null=True,
        blank=True,
        help_text="Optional explicit customer for targeted collections",
    )

    stop_type = models.CharField(
        max_length=20,
        choices=StopType.choices,
        default=StopType.HOUSE,
    )
    service_profile_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Links to service rules (waste types, frequencies, handling)",
    )
    allowed_vehicle_classes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of vehicle class codes/IDs allowed to serve this stop",
    )
    waste_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Waste category codes/IDs handled at this stop",
    )
    expected_load_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    sequence_no = models.PositiveIntegerField()
    is_mandatory = models.BooleanField(default=False)

    expected_time = models.TimeField(null=True, blank=True)
    service_window_start = models.TimeField(null=True, blank=True)
    service_window_end = models.TimeField(null=True, blank=True)
    estimated_duration_sec = models.PositiveIntegerField(default=0)

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    entrance_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text="Precise entrance point for large/stacked properties",
    )
    entrance_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    geofence = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional polygon/geojson for compounds",
    )

    access_notes = models.TextField(null=True, blank=True)
    hazard_flags = models.JSONField(
        default=list,
        blank=True,
        help_text="Flags like low_clearance, dogs, chemical_risk",
    )
    contact_name = models.CharField(max_length=100, null=True, blank=True)
    contact_phone = models.CharField(max_length=30, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        db_index=True,
    )
    actual_arrival_at = models.DateTimeField(null=True, blank=True)
    actual_departure_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="route_stops_created",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="route_stops_updated",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_route_stops"
        ordering = ["route_id", "sequence_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["route_id", "sequence_no"],
                condition=Q(is_deleted=False),
                name="uniq_route_sequence_active",
            )
        ]
        indexes = [
            models.Index(fields=["route_id"]),
            models.Index(fields=["ward"]),
            models.Index(fields=["property"]),
            models.Index(fields=["sub_property"]),
            models.Index(fields=["cluster_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["route_id", "sequence_no"]),
        ]

    def __str__(self):
        return f"{self.route_id} #{self.sequence_no} - {self.property}"
