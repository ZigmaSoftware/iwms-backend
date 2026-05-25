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

    def trigger_trip_instance(self):
        """
        Create a TripInstance if current weight meets a TripDefinition trigger.
        Returns the created instance or None.
        """
        from django.db import transaction
        from app.models.transport_masters.trip_definition import TripDefinition
        from app.models.transport_masters.trip_instance import TripInstance
        from app.models.user_creations.unassigned_staff_pool import UnassignedStaffPool

        if self.current_weight_kg is None:
            return None

        trip_def = (
            TripDefinition.objects.select_related("routeplan_id", "staff_template_id")
            .filter(
                status=TripDefinition.Status.ACTIVE,
                approval_status=TripDefinition.ApprovalStatus.APPROVED,
                property_id=self.property,
                sub_property_id=self.sub_property,
                routeplan_id__city_id=self.zone.city_id,
                routeplan_id__vehicle_id=self.vehicle,
            )
            .order_by("-created_at")
            .first()
        )

        if not trip_def or self.current_weight_kg < trip_def.trip_trigger_weight_kg:
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
                staff_template=trip_def.staff_template_id,
                alternative_staff_template=None,
                zone=self.zone,
                vehicle=self.vehicle,
                property=self.property,
                sub_property=self.sub_property,
                company_id=trip_def.company_id,
                project_id=trip_def.project_id,
                trigger_weight_kg=trip_def.trip_trigger_weight_kg,
                max_capacity_kg=trip_def.max_vehicle_capacity_kg,
                current_load_kg=self.current_weight_kg,
                start_load_kg=self.current_weight_kg,
                status=TripInstance.Status.READY,
            )

            UnassignedStaffPool.refresh_for_trip_instance(instance)

        return instance

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
