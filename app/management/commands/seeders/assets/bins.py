from app.management.commands.seeders.base import BaseSeeder

from app.models.masters.ward import Ward
from app.models.masters.panchayat import Panchayat
from app.models.assets.bins import Bins, BinType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.assets.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType


class BinSeeder(BaseSeeder):
    name = "bin"

    def _get_waste_type(self, name):
        return WasteType.objects.filter(
            waste_type_name__iexact=name, is_deleted=False
        ).first()

    def run(self):

        # --------------------------------------------------
        # COMPANY
        # --------------------------------------------------
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        # --------------------------------------------------
        # LEGACY WARD-BASED BIN (kept for back-compat)
        # --------------------------------------------------
        ward_collection_point = Collection_point.objects.filter(
            cp_name="CP 1",
            company_id=company,
            project_id=project,
        ).first()
        any_waste_type = WasteType.objects.first()

        if ward_collection_point and any_waste_type:
            Bins.objects.get_or_create(
                bin_name="Bin 1",
                company_id=company,
                project_id=project,
                defaults={
                    "collection_point_id": ward_collection_point,
                    "wastetype_id": any_waste_type,
                    "bin_capacity": 240,
                    "bin_type": BinType.MEDIUM,
                    "bin_image": "default.png",
                    "bin_qr": "QR-BIN-001",
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        # --------------------------------------------------
        # OPERATOR-FLOW BINS: wet + dry per panchayat CP
        # --------------------------------------------------
        wet_waste = self._get_waste_type("Wet Waste")
        dry_waste = self._get_waste_type("Dry Waste")
        if not wet_waste or not dry_waste:
            self.log("Wet/Dry WasteType not found — skipping panchayat bins.")
            return

        panchayat_1 = Panchayat.objects.filter(
            panchayat_name="Panchayat 1",
            company_id=company,
            project_id=project,
        ).first()

        if not panchayat_1:
            self.log("Panchayat 1 not found — skipping panchayat bins.")
            return

        cp_qs = Collection_point.objects.filter(
            panchayat_id=panchayat_1,
            company_id=company,
            project_id=project,
            is_deleted=False,
        ).order_by("cp_name")

        created_count = 0
        for cp in cp_qs:
            # extract numeric index from cp_name like "CP-PNY-01"
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

        self.log(f"---Operator-flow Bins seeded | created={created_count}---")
