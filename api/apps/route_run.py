from django.db import models, transaction

from .utils.comfun import generate_unique_id
from .route_stop import RouteStop
from .stafftemplate import StaffTemplate
from .vehicleTypeCreation import VehicleTypeCreation
from .vehicleCreation import VehicleCreation
from .userCreation import User


def generate_route_run_id():
    return f"RTRUN-{generate_unique_id()}"


class RouteRun(models.Model):
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_route_run_id,
        editable=False,
    )

    route_id = models.CharField(max_length=50, db_index=True)
    staff_template = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        related_name="route_runs",
    )
    vehicle_type = models.ForeignKey(
        VehicleTypeCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="route_runs",
    )
    vehicle = models.ForeignKey(
        VehicleCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="route_runs",
    )

    optimized_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="route_runs_created",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="route_runs_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["route_id"]),
            models.Index(fields=["is_active", "is_deleted"]),
        ]

    def __str__(self):
        return f"{self.route_id} run {self.unique_id}"

    def soft_delete(self):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

    def copy_stops_from_template(self):
        """
        Copy active template stops (RouteStop) into this run, preserving sequence_no.
        """
        stops = RouteStop.objects.filter(
            route_id=self.route_id,
            is_active=True,
            is_deleted=False,
        ).order_by("sequence_no", "id")

        run_stops = [
            RouteRunStop(
                route_run=self,
                route_stop=stop,
                sequence_no=stop.sequence_no,
            )
            for stop in stops
        ]

        with transaction.atomic():
            RouteRunStop.objects.bulk_create(run_stops)


class RouteRunStop(models.Model):
    route_run = models.ForeignKey(
        RouteRun,
        on_delete=models.CASCADE,
        related_name="stops",
    )
    route_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.CASCADE,
        related_name="run_stops",
    )
    sequence_no = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("completed", "Completed"),
            ("skipped", "Skipped"),
        ],
    )

    actual_arrival_at = models.DateTimeField(null=True, blank=True)
    actual_departure_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["route_run", "sequence_no"]
        indexes = [
            models.Index(fields=["route_run"]),
            models.Index(fields=["route_run", "sequence_no"]),
        ]

    def __str__(self):
        return f"{self.route_run_id} -> {self.route_stop_id} ({self.sequence_no})"

