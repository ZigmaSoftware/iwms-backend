# # seeders/masters/bin.py
# from django.utils import timezone

# from app.management.commands.seeders.base import BaseSeeder
# from app.models.masters.ward import Ward
# from app.models.assets.bin import Bin, BinType, WasteType, BinStatus
# from app.models.superadmin_masters.company import Company
# from app.models.superadmin_masters.project import Project


# class BinSeeder(BaseSeeder):
#     name = "bin"

#     def run(self):
#         company, _ = Company.objects.get_or_create(
#             name="IWMS",
#             defaults={
#                 "description": "Integrated Waste Management System",
#                 "is_active": True,
#                 "is_deleted": False,
#             },
#         )
#         project_name = f"{company.name} Main Project"
#         project, _ = Project.objects.get_or_create(
#             name=project_name,
#             company_id=company,
#             defaults={
#                 "description": f"Default project for {company.name}",
#                 "is_active": True,
#                 "is_deleted": False,
#             },
#         )
#         ward_1 = Ward.objects.get(name="Ward 1")

#         Bin.objects.get_or_create(
#             bin_name="Bin 1",
#             ward=ward_1,
#             company_id=company,
#             project_id=project,
#             defaults={
#                 "bin_type": BinType.PUBLIC,
#                 "waste_type": WasteType.MIXED,
#                 "color_code": "Green",
#                 "capacity_liters": 240,
#                 "latitude": 13.082680,
#                 "longitude": 80.270718,
#                 "installation_date": timezone.now().date(),
#                 "expected_life_years": 5,
#                 "bin_status": BinStatus.ACTIVE,
#                 "is_active": True,
#                 "is_deleted": False,
#             },
#         )

#         self.log("---Bins seeded---")



from app.management.commands.seeders.base import BaseSeeder

from app.models.masters.ward import Ward
from app.models.assets.bins import Bins, BinType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.assets.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType


class BinSeeder(BaseSeeder):
    name = "bin"

    def run(self):

        # --------------------------------------------------
        # COMPANY
        # --------------------------------------------------
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        # --------------------------------------------------
        # REQUIRED FOREIGN KEYS
        # --------------------------------------------------
        ward_1 = Ward.objects.get(ward_name="Ward 1")

        # You MUST already have these seeded
        collection_point = Collection_point.objects.first()
        waste_type = WasteType.objects.first()

        if not collection_point or not waste_type:
            self.log("CollectionPoint or WasteType not found. Skipping bin seed.")
            return

        # --------------------------------------------------
        # CREATE BIN
        # --------------------------------------------------
        bin_obj, created = Bins.objects.get_or_create(
            bin_name="Bin 1",
            company_id=company,
            project_id=project,
            defaults={
                "collection_point_id": collection_point,
                "wastetype_id": waste_type,
                "bin_capacity": 240,
                "bin_type": BinType.MEDIUM,
                "bin_image": "default.png",
                "bin_qr": "QR-BIN-001",
                "is_active": True,
                "is_deleted": False,
            },
        )

        action = "Created" if created else "Exists"
        self.log(f"---Bin seeded: {bin_obj.bin_name} ({action})---")