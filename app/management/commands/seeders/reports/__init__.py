from .waste_reports.daily_waste_comparison import DailyWasteComparisonSeeder
from .waste_reports.monthly_waste_comparison import MonthlyWasteComparisonSeeder

REPORT_SEEDERS = [
    DailyWasteComparisonSeeder,
    MonthlyWasteComparisonSeeder,
]
