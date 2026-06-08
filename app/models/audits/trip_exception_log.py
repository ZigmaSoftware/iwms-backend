from django.db import models
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_trip_exception_id():
    return generate_unique_id()


class TripExceptionLog(models.Model):
    """
    Immutable audit log for trip-level exceptions.
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

    class ExceptionType(models.TextChoices):
        GPS_MISMATCH = "GPS_MISMATCH", "GPS Mismatch"
        MISSED_ATTENDANCE = "MISSED_ATTENDANCE", "Missed Attendance"
        OVER_CAPACITY = "OVER_CAPACITY", "Over Capacity"
        ROUTE_DEVIATION = "ROUTE_DEVIATION", "Route Deviation"
        VEHICLE_UNAVAILABLE = "VEHICLE_UNAVAILABLE", "Vehicle Unavailable"

    class DetectedBy(models.TextChoices):
        SYSTEM = "SYSTEM", "System"
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_trip_exception_id,
        editable=False,
    )

    daily_trip_assignment = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        related_name="exception_logs",
        db_column="trip_instance_id",
        to_field="unique_id"
    )

    exception_type = models.CharField(
        max_length=30,
        choices=ExceptionType.choices
    )

    remarks = models.TextField(
        blank=True,
        null=True,
        help_text="Optional explanation or system message"
    )

    detected_by = models.CharField(
        max_length=15,
        choices=DetectedBy.choices,
        default=DetectedBy.SYSTEM
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["daily_trip_assignment"]),
            models.Index(fields=["exception_type"]),
            models.Index(fields=["detected_by"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.daily_trip_assignment_id} | {self.exception_type}"
