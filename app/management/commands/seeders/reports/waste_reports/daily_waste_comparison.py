from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.daily_waste_comparison import DailyWasteComparison
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.staff_creations.waste_collection_bluetooth import WasteType


TARGET = 30
TWO_PLACES = Decimal("0.01")


def _rounded(value):
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class DailyWasteComparisonSeeder(BaseSeeder):
    """Seed exactly 30 deterministic daily comparison rows."""

    name = "daily_waste_comparison"

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(
            name=f"{company.name} Main Project", company_id=company
        )
        panchayats = list(
            Panchayat.objects.filter(
                company_id=company,
                project_id=project,
                is_deleted=False,
            ).order_by("panchayat_name")[:15]
        )
        waste_types = list(
            WasteType.objects.filter(
                company_id=company,
                project_id=project,
                is_deleted=False,
            ).order_by("waste_type_name")[:2]
        )
        if len(panchayats) < 15 or len(waste_types) < 2:
            self.log(
                "Daily comparison skipped: requires 15 panchayats and 2 waste types."
            )
            return

        today = timezone.localdate()
        processed = 0
        for index in range(TARGET):
            panchayat = panchayats[index % len(panchayats)]
            waste_type = waste_types[index // len(panchayats)]
            collection_date = today - timedelta(days=index % 10)
            agreed = _rounded(panchayat.agreed_weight_kg or 500)
            factor = Decimal("0.82") + Decimal(index % 7) * Decimal("0.035")
            actual = _rounded(agreed * factor)
            variance = _rounded(actual - agreed)
            variance_percent = _rounded(
                variance / agreed * Decimal("100") if agreed else 0
            )
            status = "Surplus" if actual > agreed else "Deficit" if actual < agreed else "On Target"

            DailyWasteComparison.objects.update_or_create(
                unique_id=f"DWC-SEED-{index + 1:03d}",
                defaults={
                    "company_id": company,
                    "project_id": project,
                    "panchayat_id": panchayat,
                    "waste_type_id": waste_type,
                    "collection_date": collection_date,
                    "agreed_weight_kg": agreed,
                    "actual_weight_kg": actual,
                    "variance_kg": variance,
                    "variance_percent": variance_percent,
                    "report_status": status,
                    "total_trips": 12 + (index % 19),
                    "collection_points_covered": 8 + (index % 13),
                },
            )
            processed += 1

        self.log(f"---Daily waste comparison seeded ({processed} records)---")
