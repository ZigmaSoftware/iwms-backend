from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.staff_creations.waste_collection_bluetooth import WasteType
from app.models.schedule_masters.monthly_weight_report import MonthlyWeightReport
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


TARGET = 30


class MonthlyWasteComparisonSeeder(BaseSeeder):
    name = "monthly_waste_comparison"

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project", company_id=company)

        panchayats = list(Panchayat.objects.filter(
                company_id=company,
                project_id=project,
                is_deleted=False,
            ).order_by("panchayat_name")[:15])
        waste_types = list(WasteType.objects.filter(
                company_id=company,
                project_id=project,
                is_deleted=False,
            ).order_by("waste_type_name")[:2])
        if len(panchayats) < 15 or len(waste_types) < 2:
            self.log(
                "Monthly comparison skipped: requires 15 panchayats and 2 waste types."
            )
            return

        month = timezone.localdate().strftime("%Y-%m")
        processed_count = 0

        for index in range(TARGET):
            panchayat = panchayats[index % len(panchayats)]
            waste_type = waste_types[index // len(panchayats)]
            agreed_kg = _rounded(panchayat.agreed_weight_kg or 500)
            factor = Decimal("0.84") + Decimal(index % 9) * Decimal("0.03")
            actual_kg = _rounded(agreed_kg * factor)
            trips = 35 + (index % 28)
            points = 22 + (index % 21)

            variance_kg = _rounded(Decimal(str(actual_kg)) - Decimal(str(agreed_kg)))
            variance_pct = _variance_percent(actual_kg, agreed_kg)
            report_status = _status(actual_kg, agreed_kg)

            report, created = MonthlyWeightReport.objects.update_or_create(
                panchayat_id=panchayat,
                waste_type_id=waste_type,
                month=month,
                defaults={
                    "company_id": company,
                    "project_id": project,
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
                f"{panchayat.panchayat_name} | {waste_type.waste_type_name} | "
                f"{month} → {report_status} ({action})"
            )
            processed_count += 1

        self.log(
            f"---Monthly waste comparison seeded: "
            f"{processed_count} records processed---"
        )
