from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.assets.collection_point import Collection_point
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)


class DailyTripCollectionPointSeeder(BaseSeeder):
    name = "daily_trip_collection_point"

    def run(self):
        today = timezone.localdate()
        assignments = (
            DailyTripAssignment.objects
            .filter(trip_date=today, is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related("panchayat_id", "waste_type_id")
        )

        if not assignments.exists():
            self.log("No DailyTripAssignment for today — skipping.")
            return

        total_created = 0
        for assignment in assignments:
            cps = (
                Collection_point.objects
                .filter(
                    panchayat_id=assignment.panchayat_id,
                    company_id=assignment.company_id,
                    project_id=assignment.project_id,
                    is_deleted=False,
                )
                .order_by("cp_name")
            )

            sequence = 0
            for cp in cps:
                bin_obj = Bins.objects.filter(
                    collection_point_id=cp,
                    wastetype_id=assignment.waste_type_id,
                    is_deleted=False,
                ).first()
                if not bin_obj:
                    continue
                sequence += 1
                _, created = DailyTripCollectionPoint.objects.get_or_create(
                    trip_assignment_id=assignment,
                    collection_point_id=cp,
                    defaults={
                        "bin_id": bin_obj,
                        "sequence": sequence,
                        "is_collected": False,
                        "status": DailyTripCollectionPoint.STATUS_PENDING,
                    },
                )
                if created:
                    total_created += 1

        self.log(
            f"---DailyTripCollectionPoint seeded | created={total_created}---"
        )
