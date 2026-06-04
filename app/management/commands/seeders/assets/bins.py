from app.management.commands.seeders.base import BaseSeeder

from app.models.masters.ward import Ward
from app.models.masters.panchayat import Panchayat
from app.models.assets.bins import Bins, BinType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType


class BinSeeder(BaseSeeder):
    name = "bin"

    def _get_waste_type(self, name):
        return WasteType.objects.filter(
            waste_type_name__iexact=name, is_deleted=False
        ).first()

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        wet_waste = self._get_waste_type("Wet Waste")
        dry_waste = self._get_waste_type("Dry Waste")
        any_waste = wet_waste or WasteType.objects.filter(is_deleted=False).first()

        # Ward CP bin (1 record)
        ward_cp = Collection_point.objects.filter(
            cp_name="CP 1",
            company_id=company,
            project_id=project,
        ).first()

        created_count = 0

        if ward_cp and any_waste:
            _, created = Bins.objects.get_or_create(
                bin_name="Bin 1",
                company_id=company,
                project_id=project,
                defaults={
                    "collection_point_id": ward_cp,
                    "wastetype_id": any_waste,
                    "bin_capacity": 240,
                    "bin_type": BinType.MEDIUM,
                    "bin_image": "default.png",
                    "bin_qr": "QR-BIN-001",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                created_count += 1

        if not wet_waste or not dry_waste:
            self.log("Wet/Dry WasteType not found — skipping panchayat bins.")
            return

        # Panchayat CPs — wet + dry bin each (up to 14 bins across panchayat CPs)
        panchayat_cps = Collection_point.objects.filter(
            company_id=company,
            project_id=project,
            ward_id__isnull=True,
            is_deleted=False,
        ).order_by("panchayat_id", "cp_name")[:7]  # 7 CPs × 2 bins = 14 bins

        for cp in panchayat_cps:
            try:
                idx = int(cp.cp_name.split("-")[-1])
            except (ValueError, IndexError):
                idx = 0

            for label, waste_type in (("WET", wet_waste), ("DRY", dry_waste)):
                qr = f"QR-CP{idx:02d}-{label}"
                bin_name = f"{cp.cp_name} {label.capitalize()} Bin"
                _, created = Bins.objects.get_or_create(
                    bin_qr=qr,
                    company_id=company,
                    project_id=project,
                    defaults={
                        "collection_point_id": cp,
                        "wastetype_id": waste_type,
                        "bin_name": bin_name,
                        "bin_capacity": 240,
                        "bin_type": BinType.MEDIUM,
                        "bin_image": "default.png",
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    created_count += 1

        self.log(f"---Bins seeded | created={created_count} (1 ward + up to 14 panchayat bins)---")
