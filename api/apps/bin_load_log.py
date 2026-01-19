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

    def trigger_trip_instance(self):
        """
        Create a TripInstance if this log meets a TripDefinition trigger.
        Returns the created instance or None.
        """
        if self.processed:
            return None

        from django.db import transaction
        from api.apps.trip_definition import TripDefinition
        from api.apps.trip_instance import TripInstance
        from api.apps.unassigned_staff_pool import UnassignedStaffPool

        trip_def = (
            TripDefinition.objects.select_related("routeplan", "staff_template")
            .filter(
                status=TripDefinition.Status.ACTIVE,
                approval_status=TripDefinition.ApprovalStatus.APPROVED,
                property=self.property,
                sub_property=self.sub_property,
                routeplan__zone_id=self.zone.unique_id,
                routeplan__vehicle_id=self.vehicle.id,
            )
            .order_by("-created_at")
            .first()
        )

        if not trip_def:
            return None

        if self.weight_kg < trip_def.trip_trigger_weight_kg:
            return None

        existing = TripInstance.objects.filter(
            trip_definition=trip_def,
            zone=self.zone,
            vehicle=self.vehicle,
            property=self.property,
            sub_property=self.sub_property,
            status__in=[
                TripInstance.Status.WAITING_FOR_LOAD,
                TripInstance.Status.READY,
                TripInstance.Status.IN_PROGRESS,
            ],
        ).exists()

        if existing:
            return None

        with transaction.atomic():
            instance = TripInstance.objects.create(
                trip_definition=trip_def,
                staff_template=trip_def.staff_template,
                alternative_staff_template=None,
                zone=self.zone,
                vehicle=self.vehicle,
                property=self.property,
                sub_property=self.sub_property,
                trigger_weight_kg=trip_def.trip_trigger_weight_kg,
                max_capacity_kg=trip_def.max_vehicle_capacity_kg,
                current_load_kg=self.weight_kg,
                start_load_kg=self.weight_kg,
                status=TripInstance.Status.READY,
            )
            self.processed = True
            self.save(update_fields=["processed"])

            UnassignedStaffPool.refresh_for_trip_instance(instance)

        return instance
