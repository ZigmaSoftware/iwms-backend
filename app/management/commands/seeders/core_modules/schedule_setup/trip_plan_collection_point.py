from app.management.commands.seeders.base import BaseSeeder
from django.db.models import Max
from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)


class TripPlanCollectionPointSeeder(BaseSeeder):
    name = "trip_plan_collection_point"

    def run(self):
        total_created = 0
        # Bin-only: this seeder exclusively looks up Collection_point/Bins,
        # so it must not run against household/bulk plans (see TripPlanSeeder's
        # household-collection block) — those get their single HOUSEHOLD-type
        # stop created directly by TripPlanSeeder instead.
        plans = TripPlan.objects.filter(
            is_deleted=False,
            status=TripPlan.Status.ACTIVE,
            collection_type=TripPlan.COLLECTION_TYPE_BIN,
        )

        for plan in plans:
            cps = Collection_point.objects.filter(
                company_id=plan.company_id,
                project_id=plan.project_id,
                is_deleted=False,
            )
            if plan.panchayat_id:
                cps = cps.filter(panchayat_id=plan.panchayat_id)
            else:
                plan_wards = plan.wards.all()
                if plan_wards.exists():
                    cps = cps.filter(wards__in=plan_wards).distinct()
            cps = cps.order_by("cp_name")

            sequence = (
                TripPlanCollectionPoint.objects
                .filter(trip_plan_id=plan, is_deleted=False)
                .aggregate(max_sequence=Max("sequence"))
                .get("max_sequence")
                or 0
            )
            for cp in cps:
                bin_obj = Bins.objects.filter(
                    collection_point_id=cp,
                    wastetype_id__unique_id__in=plan.waste_type_ids or [plan.waste_type_id_id],
                    is_deleted=False,
                ).first()
                if not bin_obj:
                    bin_obj = Bins.objects.filter(
                        collection_point_id=cp,
                        is_deleted=False,
                    ).first()
                if not bin_obj:
                    continue

                existing_stop = TripPlanCollectionPoint.objects.filter(
                    trip_plan_id=plan,
                    collection_point_id=cp,
                    bin_id=bin_obj,
                    is_deleted=False,
                ).first()
                if existing_stop:
                    if not existing_stop.is_active:
                        existing_stop.is_active = True
                        existing_stop.save(update_fields=["is_active"])
                    continue

                sequence += 1
                TripPlanCollectionPoint.objects.create(
                    trip_plan_id=plan,
                    collection_point_id=cp,
                    bin_id=bin_obj,
                    sequence=sequence,
                    is_active=True,
                )
                total_created += 1

        self.log(f"---TripPlanCollectionPoint seeded | created={total_created}---")
