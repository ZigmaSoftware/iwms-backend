from django.db import models
from api.apps.trip_instance import TripInstance
from api.apps.vehicleCreation import VehicleCreation


class VehicleTripAudit(models.Model):
    """
    GPS & motion audit for trip replay, idle detection,
    and compliance analysis.
    """

    id = models.BigAutoField(primary_key=True)

    trip_instance = models.ForeignKey(
        TripInstance,
        on_delete=models.PROTECT,
        related_name="vehicle_audits",
        db_column="trip_instance_id",
        to_field="unique_id"
    )

    vehicle = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        related_name="trip_audits",
        db_column="vehicle_id",
        to_field="unique_id"
    )

    # GPS batches (every 5 sec samples)
    gps_lat = models.JSONField(
        help_text="Latitude samples (DECIMAL(10,7))"
    )
    gps_lon = models.JSONField(
        help_text="Longitude samples (DECIMAL(10,7))"
    )

    avg_speed = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Average speed during capture window (km/h)"
    )

    idle_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Idle time in seconds within this capture window"
    )

    captured_at = models.DateTimeField(
        help_text="Timestamp of capture window end"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_vehicle_trip_audit"
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["trip_instance", "vehicle"]),
            models.Index(fields=["captured_at"]),
        ]

    def __str__(self):
        return f"{self.trip_instance_id} | {self.vehicle_id} | {self.captured_at}"
