from django.db import models
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_vehicle_trip_audit_id():
    return f"VTA-{generate_unique_id()}"    


class VehicleTripAudit(models.Model):
    """
    GPS & motion audit for trip replay, idle detection,
    and compliance analysis.
    """
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_vehicle_trip_audit_id,
        editable=False,
    )

    daily_trip_assignment = models.ForeignKey(
        DailyTripAssignment,
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
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["daily_trip_assignment", "vehicle"]),
            models.Index(fields=["captured_at"]),
        ]

    def __str__(self):
        return f"{self.daily_trip_assignment_id} | {self.vehicle_id} | {self.captured_at}"
