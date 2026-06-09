from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)


class DailyTripCollectionPointSeeder(BaseSeeder):
    name = "daily_trip_collection_point"

    def run(self):
        today = timezone.localdate()
        assignments = (
            DailyTripAssignment.objects
            .filter(is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related(
                "company_id",
                "project_id",
                "panchayat_id",
                "ward_id",
                "waste_type_id",
            )
            .order_by("-trip_date", "-scheduled_time")
        )

        if not assignments.exists():
            self.log("No DailyTripAssignment found — skipping.")
            return

        total_created = 0
        total_reset = 0
        for assignment in assignments:
            cp_qs = Collection_point.objects.filter(
                company_id=assignment.company_id,
                project_id=assignment.project_id,
                is_deleted=False,
            )
            if assignment.panchayat_id:
                cp_qs = cp_qs.filter(panchayat_id=assignment.panchayat_id)
            elif assignment.ward_id:
                cp_qs = cp_qs.filter(ward_id=assignment.ward_id)
            cps = list(cp_qs.order_by("cp_name"))

            if not cps:
                cps = list(
                    Collection_point.objects
                    .filter(
                        company_id=assignment.company_id,
                        project_id=assignment.project_id,
                        is_deleted=False,
                    )
                    .order_by("cp_name")[:5]
                )

            sequence = 0
            for cp in cps:
                bin_obj = Bins.objects.filter(
                    collection_point_id=cp,
                    wastetype_id=assignment.waste_type_id,
                    is_deleted=False,
                ).first()
                if not bin_obj:
                    bin_obj = Bins.objects.filter(
                        collection_point_id=cp,
                        is_deleted=False,
                    ).first()
                if not bin_obj:
                    continue
                sequence += 1
                trip_cp, created = DailyTripCollectionPoint.objects.get_or_create(
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
                elif (
                    assignment.trip_date == today
                    and (
                        trip_cp.is_collected
                        or trip_cp.status != DailyTripCollectionPoint.STATUS_PENDING
                        or trip_cp.collected_at is not None
                        or trip_cp.collected_weight_kg is not None
                        or trip_cp.collected_by_id is not None
                    )
                ):
                    trip_cp.is_collected = False
                    trip_cp.status = DailyTripCollectionPoint.STATUS_PENDING
                    trip_cp.collected_at = None
                    trip_cp.collected_weight_kg = None
                    trip_cp.collected_by = None
                    trip_cp.save(
                        update_fields=[
                            "is_collected",
                            "status",
                            "collected_at",
                            "collected_weight_kg",
                            "collected_by",
                            "updated_at",
                        ]
                    )
                    total_reset += 1

            if assignment.trip_date == today:
                BinCollectionEvent.objects.filter(
                    trip_assignment_id=assignment,
                    is_deleted=False,
                ).update(is_deleted=True)
                if assignment.status == DailyTripAssignment.STATUS_COMPLETED:
                    assignment.status = DailyTripAssignment.STATUS_IN_PROGRESS
                    assignment.actual_end_time = None
                    assignment.save(
                        update_fields=[
                            "status",
                            "actual_end_time",
                            "updated_at",
                        ]
                    )

        self.log(
            f"---DailyTripCollectionPoint seeded | created={total_created} | today_reset={total_reset}---"
        )
