from app.management.commands.seeders.base import BaseSeeder
from app.models.complaints.main_category_citizenGrievance import MainCategory


class MainCategorySeeder(BaseSeeder):
    name = "main_category"

    def run(self):
        main_categories = [
            "Report issue",
            "Schedule pickup",
            "Pickup status",
            "Waste tips",
            "Collector info",
        ]

        for category in main_categories:
            MainCategory.objects.get_or_create(
                main_categoryName=category,  
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        self.log("Main categories seeded")
