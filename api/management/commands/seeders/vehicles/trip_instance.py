from django.utils import timezone

from api.management.commands.seeders.base import BaseSeeder
from api.apps.trip_definition import TripDefinition
from api.apps.trip_instance import TripInstance
from api.apps.bin_load_log import BinLoadLog
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation


class TripInstanceSeeder(BaseSeeder):
    name = "trip_instance"

    def run(self):
        trip_def = (
            TripDefinition.objects.filter(
                status=TripDefinition.Status.ACTIVE,
                approval_status=TripDefinition.ApprovalStatus.APPROVED,
            )
            .order_by("-created_at")
            .first()
        )
        if not trip_def:
            self.log("TripInstanceSeeder skipped (no approved trip definition).")
            return

        existing_active = TripInstance.objects.filter(
            trip_definition=trip_def,
            status__in=[
                TripInstance.Status.WAITING_FOR_LOAD,
                TripInstance.Status.READY,
                TripInstance.Status.IN_PROGRESS,
            ],
        ).exists()
        if existing_active:
            self.log("TripInstanceSeeder skipped (active trip instance exists).")
            return

        routeplan = trip_def.routeplan_id
        zone = Zone.objects.filter(city_id=routeplan.city_id).first()
        if not zone:
            zone = Zone.objects.first()
        vehicle = routeplan.vehicle_id

        if not zone or not vehicle:
            self.log("TripInstanceSeeder skipped (routeplan mapping missing).")
            return

        bin_log = (
            BinLoadLog.objects.filter(
                processed=False,
                zone=zone,
                vehicle=vehicle,
                property=trip_def.property_id,
                sub_property=trip_def.sub_property_id,
            )
            .order_by("-event_time")
            .first()
        )

        if not bin_log:
            bin_log = BinLoadLog.objects.create(
                zone=zone,
                vehicle=vehicle,
                property=trip_def.property_id,
                sub_property=trip_def.sub_property_id,
                weight_kg=trip_def.trip_trigger_weight_kg,
                source_type=BinLoadLog.SourceType.MANUAL,
                event_time=timezone.now(),
                processed=False,
            )
        else:
            updates = {}
            if bin_log.weight_kg < trip_def.trip_trigger_weight_kg:
                updates["weight_kg"] = trip_def.trip_trigger_weight_kg
            if bin_log.processed:
                updates["processed"] = False
            if updates:
                BinLoadLog.objects.filter(pk=bin_log.pk).update(**updates)
                for field, value in updates.items():
                    setattr(bin_log, field, value)

        instance = bin_log.trigger_trip_instance()
        if instance:
            self.log("TripInstance seeded")
        else:
            self.log("TripInstanceSeeder skipped (trigger not met).")
