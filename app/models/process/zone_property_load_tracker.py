from django.db import models
from app.models.masters.zone import Zone
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.utils.comfun import generate_unique_id
from django.utils import timezone
from app.models.audits.bin_load_log import BinLoadLog


def generate_zone_property_load_tracker_id():
    return f"ZPLT-{generate_unique_id()}"   


class ZonePropertyLoadTracker(models.Model):
    """
    Live state table.
    Tracks pending, undispatched load per zone + property (+ vehicle).
    """
    
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_zone_property_load_tracker_id,
        editable=False,
    )
    
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

    def trigger_daily_trip_assignment(self):
        """
        Automatic dispatch is handled by the Schedule Masters daily assignment flow.
        """
        return None

    def create_audit_log(self, event_time=None, source_type=None):
        """
        Create a BinLoadLog audit record for the current tracker state.
        """
        if event_time is None:
            event_time = timezone.now()

        # Default to SENSOR as the source for tracker-originated logs
        source = source_type if source_type is not None else BinLoadLog.SourceType.SENSOR

        weight = self.current_weight_kg or 0

        try:
            BinLoadLog.objects.create(
                zone=self.zone,
                vehicle=self.vehicle,
                property=self.property,
                sub_property=self.sub_property,
                weight_kg=weight,
                source_type=source,
                event_time=event_time,
                processed=False,
            )
        except Exception:
            # If the audit table isn't present yet (migrations not applied) or
            # any other DB issue occurs, skip creating the audit log to
            # avoid breaking creation/update flows.
            return None
