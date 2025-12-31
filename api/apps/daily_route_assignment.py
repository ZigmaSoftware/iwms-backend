from django.db import models

from .utils.comfun import generate_unique_id
from .stafftemplate import StaffTemplate
from .vehicleTypeCreation import VehicleTypeCreation
from .route_run import RouteRun


def generate_daily_route_assignment_id():
    return f"DRASSIGN-{generate_unique_id()}"


class DailyRouteAssignment(models.Model):
    """
    Temporary daily assignment binder for the new route-based system.
    """

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_daily_route_assignment_id,
        editable=False,
    )

    vehicle_type = models.ForeignKey(
        VehicleTypeCreation,
        on_delete=models.PROTECT,
        related_name="daily_route_assignments",
    )
    staff_template = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        related_name="daily_route_assignments",
    )
    route_run = models.ForeignKey(
        RouteRun,
        on_delete=models.PROTECT,
        related_name="daily_assignments",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "api_daily_route_assignments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "is_deleted"]),
        ]

    def __str__(self):
        return f"{self.route_run.route_id} -> {self.vehicle_type}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
