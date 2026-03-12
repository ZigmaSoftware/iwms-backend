from datetime import date, datetime
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.assets.point_collection import PointCollection
from app.models.assets.bins import Bins
from app.models.assets.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.transport_masters.trip import Trip
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class PointCollectionSeeder(BaseSeeder):
    name = "point_collection"

    def run(self):

        # --------------------------------------------------
        # COMPANY & PROJECT
        # --------------------------------------------------
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        # --------------------------------------------------
        # REQUIRED FOREIGN KEYS
        # --------------------------------------------------
        bin_obj = Bins.objects.first()
        collection_point = Collection_point.objects.first()
        waste_type = WasteType.objects.first()
        trip = Trip.objects.first()

        if not all([bin_obj, collection_point, waste_type, trip]):
            self.log("Missing dependency (Bin / CollectionPoint / WasteType / Trip). Skipping PointCollection.")
            return

        # --------------------------------------------------
        # CREATE / UPDATE POINT COLLECTION
        # --------------------------------------------------
        pc, created = PointCollection.objects.update_or_create(
            bin_id=bin_obj,
            trip_id=trip,
            collection_date=date.today(),
            defaults={
                "waste_type_id": waste_type,
                "collection_point_id": collection_point,
                "point_collection_weight": 25.50,
                "collection_time": timezone.now().time(),
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
            },
        )

        action = "Created" if created else "Updated"
        self.log(f"---PointCollection seeded: {pc.unique_id} ({action})---")