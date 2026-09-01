"""Waste report seeders — daily and monthly collected-waste comparisons."""

from .daily_waste_comparison import DailyWasteComparisonSeeder
from .monthly_waste_comparison import MonthlyWasteComparisonSeeder

WASTE_REPORT_SEEDERS = [
    DailyWasteComparisonSeeder,
    MonthlyWasteComparisonSeeder,
]

__all__ = [
    "DailyWasteComparisonSeeder",
    "MonthlyWasteComparisonSeeder",
    "WASTE_REPORT_SEEDERS",
]
