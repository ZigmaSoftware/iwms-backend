from django.db import models
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class ZonePropertyLoadTracker(models.Model):
    """
    Live state table.
    Tracks pending, undispatched load per zone + property (+ vehicle).
    """

    id = models.BigAutoField(primary_key=True)

    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="zone_load_trackers"
    )

    vehicle = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        related_name="zone_load_trackers"
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="zone_load_trackers"
    )

    sub_property = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        related_name="zone_load_trackers"
    )

    current_weight_kg = models.PositiveIntegerField(default=0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_zone_property_load_tracker"
        verbose_name = "Zone Property Load Tracker"
        verbose_name_plural = "Zone Property Load Trackers"
        unique_together = (
            "zone",
            "vehicle",
            "property",
            "sub_property",
        )
        indexes = [
            models.Index(fields=["zone", "vehicle"]),
            models.Index(fields=["property", "sub_property"]),
        ]

    def __str__(self):
        return f"{self.zone.name} | {self.property.property_name} | {self.current_weight_kg} kg"
