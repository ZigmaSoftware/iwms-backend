from django.db import models
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty
from api.apps.bin import Bin
from .utils.comfun import generate_unique_id


def generate_bin_load_log_id():
    return f"BLL-{generate_unique_id()}"


class BinLoadLog(models.Model):

    class SourceType(models.TextChoices):
        WEIGHBRIDGE = "WEIGHBRIDGE", "Weighbridge"
        SENSOR = "SENSOR", "Sensor"
        MANUAL = "MANUAL", "Manual"

    # ---------- Identity ----------
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_bin_load_log_id,
        editable=False,
    )

    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="bin_load_logs"
    )

    vehicle = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        related_name="bin_load_logs"
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="bin_load_logs"
    )

    sub_property = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        related_name="bin_load_logs"
    )

    bin = models.ForeignKey(
        Bin,
        on_delete=models.PROTECT,
        related_name="load_logs",
        to_field="unique_id",
        db_column="bin_id",
        null=True,
        blank=True,
        help_text="The specific bin this load was collected from"
    )

    weight_kg = models.PositiveIntegerField()

    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices
    )

    event_time = models.DateTimeField()
    processed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_bin_load_log"
        ordering = ["-event_time"]

    def __str__(self):
        return f"{self.zone.name} | {self.weight_kg} kg | {self.source_type}"
