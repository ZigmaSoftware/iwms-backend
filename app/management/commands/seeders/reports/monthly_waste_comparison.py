import uuid
from decimal import Decimal, ROUND_HALF_UP

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.reports.monthly_weight_report import MonthlyWeightReport
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


TWO_PLACES = Decimal("0.01")


def _rounded(value):
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _variance_percent(actual, agreed):
    if agreed == 0:
        return Decimal("0")
    return _rounded((Decimal(str(actual)) - Decimal(str(agreed))) / Decimal(str(agreed)) * 100)


def _status(actual, agreed):
    actual = Decimal(str(actual))
    agreed = Decimal(str(agreed))
    if actual > agreed:
        return "Surplus"
    if actual < agreed:
        return "Deficit"
    return "On Target"


# (panchayat_name, waste_type_name, month, agreed_kg, actual_kg, trips, points_covered)
SAMPLE_RECORDS = [
    # Panchayat 1 – Dry Waste
    ("Panchayat 1", "Dry Waste", "2026-01", 500, 480, 60, 55),
    ("Panchayat 1", "Dry Waste", "2026-02", 500, 515, 62, 57),
    ("Panchayat 1", "Dry Waste", "2026-03", 500, 490, 58, 52),
    ("Panchayat 1", "Wet Waste", "2026-01", 300, 290, 40, 38),
    ("Panchayat 1", "Wet Waste", "2026-02", 300, 310, 42, 40),

    # Panchayat 2 – Dry & Wet
    ("Panchayat 2", "Dry Waste", "2026-01", 750, 700, 80, 75),
    ("Panchayat 2", "Dry Waste", "2026-02", 750, 780, 82, 78),
    ("Panchayat 2", "Dry Waste", "2026-03", 750, 720, 78, 72),
    ("Panchayat 2", "Wet Waste", "2026-01", 400, 360, 50, 45),
    ("Panchayat 2", "Wet Waste", "2026-02", 400, 420, 52, 48),

    # Panchayat 3 – Dry Waste only
    ("Panchayat 3", "Dry Waste", "2026-01", 600, 550, 70, 65),
    ("Panchayat 3", "Dry Waste", "2026-02", 600, 610, 72, 68),
    ("Panchayat 3", "Dry Waste", "2026-03", 600, 580, 68, 62),

    # Panchayat 4 – Mixed Waste
    ("Panchayat 4", "Dry Waste", "2026-01", 450, 430, 55, 50),
    ("Panchayat 4", "Wet Waste", "2026-01", 250, 270, 35, 33),
    ("Panchayat 4", "Dry Waste", "2026-02", 450, 440, 56, 51),

    # Panchayat 5 – High volume
    ("Panchayat 5", "Dry Waste", "2026-01", 820, 810, 90, 85),
    ("Panchayat 5", "Dry Waste", "2026-02", 820, 850, 92, 88),
    ("Panchayat 5", "Wet Waste", "2026-01", 500, 480, 65, 60),
    ("Panchayat 5", "Wet Waste", "2026-02", 500, 520, 67, 63),
]


class MonthlyWasteComparisonSeeder(BaseSeeder):
    name = "monthly_waste_comparison"

    def run(self):
        company = Company.objects.get(name="IWMS")

        created_count = 0
        skipped_count = 0

        for (panchayat_name, waste_type_name, month,
             agreed_kg, actual_kg, trips, points) in SAMPLE_RECORDS:

            panchayat = Panchayat.objects.filter(
                panchayat_name=panchayat_name,
                company_id=company,
                is_deleted=False,
            ).first()
            if not panchayat:
                self.log(f"Panchayat '{panchayat_name}' not found – skipping")
                skipped_count += 1
                continue

            waste_type = WasteType.objects.filter(
                waste_type_name=waste_type_name,
                is_deleted=False,
            ).first()
            if not waste_type:
                self.log(f"WasteType '{waste_type_name}' not found – skipping")
                skipped_count += 1
                continue

            variance_kg = _rounded(Decimal(str(actual_kg)) - Decimal(str(agreed_kg)))
            variance_pct = _variance_percent(actual_kg, agreed_kg)
            report_status = _status(actual_kg, agreed_kg)

            _, created = MonthlyWeightReport.objects.update_or_create(
                panchayat_id=panchayat,
                waste_type_id=waste_type,
                month=month,
                defaults={
                    "unique_id": f"MWR-{uuid.uuid4().hex[:16].upper()}",
                    "agreed_weight_kg": agreed_kg,
                    "actual_weight_kg": actual_kg,
                    "variance_kg": variance_kg,
                    "variance_percent": variance_pct,
                    "report_status": report_status,
                    "total_trips": trips,
                    "collection_points_covered": points,
                },
            )
            action = "Created" if created else "Updated"
            self.log(
                f"{panchayat_name} | {waste_type_name} | {month} "
                f"→ agreed={agreed_kg}, actual={actual_kg}, status={report_status} ({action})"
            )
            created_count += 1

        self.log(
            f"Monthly waste comparison seeding done: "
            f"{created_count} processed, {skipped_count} skipped."
        )
