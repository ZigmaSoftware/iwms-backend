from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class BinCollectionEventSeeder(BaseSeeder):
    name = "bin_collection_event"

    def run(self):
        company = Company.objects.filter(name="IWMS").first()
        project = Project.objects.filter(
            name=f"{company.name} Main Project"
        ).first() if company else None

        if not company or not project:
            self.log("Company/Project not found — skipping.")
            return

        assignments = (
            DailyTripAssignment.objects
            .filter(
                company_id=company,
                project_id=project,
                is_deleted=False,
            )
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .order_by("-trip_date")[:3]
        )

        if not assignments.exists():
            self.log("No DailyTripAssignment found — skipping.")
            return

        created_count = 0
        for assignment in assignments:
            trip_cps = (
                DailyTripCollectionPoint.objects
                .filter(trip_assignment_id=assignment, is_deleted=False)
                .select_related("collection_point_id", "bin_id")
                .order_by("sequence")
            )

            if not trip_cps.exists():
                continue

            for trip_cp in trip_cps:
                if not trip_cp.bin_id:
                    continue

                if BinCollectionEvent.objects.filter(
                    trip_collection_point_id=trip_cp
                ).exists():
                    continue

                bin_obj = trip_cp.bin_id

                BinCollectionEvent.objects.create(
                    company_id=company,
                    project_id=project,
                    trip_assignment_id=assignment,
                    trip_collection_point_id=trip_cp,
                    collection_point_id=trip_cp.collection_point_id,
                    bin_id=bin_obj,
                    waste_type_id=getattr(bin_obj, "wastetype_id", None),
                    vehicle_id=getattr(assignment, "vehicle_id", None),
                    panchayat_id=assignment.panchayat_id,
                    collected_weight_kg=round(
                        float(bin_obj.bin_capacity or 240) * 0.65, 2
                    ),
                    driver_latitude=13.083000,
                    driver_longitude=80.271000,
                    notes="Seeded sample scan event",
                )
                created_count += 1

        self.log(
            f"---BinCollectionEvent seeded | created={created_count}---"
        )
