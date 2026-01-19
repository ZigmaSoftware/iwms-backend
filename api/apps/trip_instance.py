from django.db import models
from api.apps.trip_definition import TripDefinition
from api.apps.stafftemplate import StaffTemplate
from api.apps.alternative_staff_template import AlternativeStaffTemplate
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty
from api.apps.utils.comfun import generate_unique_id


def generate_trip_instance_id():
    return f"TRIPINST-{generate_unique_id()}"


def generate_trip_no():
    return f"TRIP-{generate_unique_id()}"


class TripInstance(models.Model):

    class Status(models.TextChoices):
        WAITING_FOR_LOAD = "WAITING_FOR_LOAD", "Waiting for Load"
        READY = "READY", "Ready"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    unique_id = models.CharField(
        max_length=36,
        unique=True,
        default=generate_trip_instance_id,
        editable=False
    )

    trip_no = models.CharField(
        max_length=30,
        unique=True,
        default=generate_trip_no,
        editable=False
    )

    trip_definition = models.ForeignKey(
        TripDefinition,
        on_delete=models.PROTECT,
        related_name="trip_instances"
    )

    staff_template = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        related_name="trip_instances",
        db_column="staff_template_id",
        to_field="unique_id"
    )

    alternative_staff_template = models.ForeignKey(
        AlternativeStaffTemplate,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trip_instances"
    )

    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="trip_instances"
    )

    vehicle = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        related_name="trip_instances",
        db_column="vehicle_id",
        to_field="unique_id"
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="trip_instances"
    )

    sub_property = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        related_name="trip_instances"
    )

    trigger_weight_kg = models.PositiveIntegerField()
    max_capacity_kg = models.PositiveIntegerField()

    current_load_kg = models.PositiveIntegerField(default=0)
    start_load_kg = models.PositiveIntegerField(default=0)
    end_load_kg = models.PositiveIntegerField(default=0)

    trip_start_time = models.DateTimeField(null=True, blank=True)
    trip_end_time = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING_FOR_LOAD
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_trip_instance"
        verbose_name = "Trip Instance"
        verbose_name_plural = "Trip Instances"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["zone", "vehicle"]),
        ]

    def __str__(self):
        return self.trip_no
