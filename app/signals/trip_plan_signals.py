from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)


@receiver(post_save, sender=DailyTripAssignment)
def copy_trip_plan_stops_to_daily_assignment(sender, instance, created, **kwargs):
    if not created or not instance.trip_plan_id_id:
        return

    plan_stops = TripPlanCollectionPoint.objects.filter(
        trip_plan_id=instance.trip_plan_id,
        is_active=True,
        is_deleted=False,
    ).order_by("sequence")

    for stop in plan_stops:
        DailyTripCollectionPoint.objects.get_or_create(
            trip_assignment_id=instance,
            collection_point_id=stop.collection_point_id,
            defaults={
                "bin_id": stop.bin_id,
                "sequence": stop.sequence,
                "is_collected": False,
                "status": DailyTripCollectionPoint.STATUS_PENDING,
                "created_by": getattr(instance, "created_by", None),
            },
        )
